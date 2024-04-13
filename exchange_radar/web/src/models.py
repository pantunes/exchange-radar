import logging
import time
from datetime import datetime, timedelta

from pydantic import BaseModel, computed_field
from redis_om import Field, JsonModel, Migrator, get_redis_connection

from exchange_radar.web.src.settings import base as settings
from exchange_radar.web.src.types import ERdefaultdict

logger = logging.getLogger(__name__)


redis = get_redis_connection()

cache_pks = ERdefaultdict(list)


class Feed(JsonModel):  # pragma: no cover
    """
    All fields:
    {
        "symbol": "ETHUSDT",
        "price": "2549.83000000",
        "quantity": "0.60660000",
        "trade_time": "2024-01-10T22:37:02",
        "is_seller": False,
        "total": "1546.7268780000",
        "currency": "USDT",
        "trade_symbol": "ETH",
        "volume": 77490.03932637,
        "volume_trades": [38839.13855542, 38650.71084956],
        "number_trades": [96918, 95907],
        "message": "2024-01-10 22:37:02 | <span class='binance'>Binance </span> |  2549.83000000 USDT | ....."
        "exchange": "Binance",
    }
    Thin version:
    {
        "price": "2549.83000000",
        "is_seller": False,
        "currency": "USDT",
        "trade_symbol": "ETH",
        "volume": 77490.03932637,
        "volume_trades": [38839.13855542, 38650.71084956],
        "number_trades": [96918, 95907],
        "message": "2024-01-10 22:37:02 | <span class='binance'>Binance </span> |  2549.83000000 USDT | ....."
    }
    """

    type: str = Field(index=True)
    price: float
    trade_time_ts: int = Field(index=True, sortable=True)
    is_seller: bool
    currency: str
    trade_symbol: str = Field(index=True)
    volume: float
    volume_trades: list[float]
    number_trades: list[int]
    message: str

    @classmethod
    def is_coin_selected(cls, coin: str, category: str) -> bool:
        return coin in ("LTO",) or category in (
            "FeedWhales",
            "FeedDolphins",
        )

    @classmethod
    def select_rows(cls, coin: str, category: str) -> list[dict[str, str]]:
        return [
            item.dict()
            for item in cls.find((cls.trade_symbol == coin) & (cls.type == category))
            .sort_by("-trade_time_ts")
            .page(offset=0, limit=settings.REDIS_MAX_ROWS)
        ][::-1]

    @classmethod
    def save_or_not(cls, coin: str, category: str, message: dict) -> bool:
        if cls.is_coin_selected(coin, category):
            obj = cls(
                type=category,
                price=message["price"],
                trade_time_ts=message["trade_time_ts"],
                is_seller=message["is_seller"],
                currency=message["currency"],
                trade_symbol=message["trade_symbol"],
                volume=message["volume"],
                volume_trades=message["volume_trades"],
                number_trades=message["number_trades"],
                message=message["message"],
            ).save()

            cache_pks.__get__(coin=coin, category=category).append(obj.pk)
            logger.info(f"CACHE_PKS: {cache_pks}")

            count = cls.find((cls.trade_symbol == coin) & (cls.type == category)).count()
            logger.info(f"COUNT: {count}")

            if count > settings.REDIS_MAX_ROWS:
                obj2del_pk = cache_pks.__get__(coin=coin, category=category).pop(0)
                is_deleted = cls.delete(obj2del_pk)
                logger.info(f"DELETE {obj2del_pk} RETURN {is_deleted}")

            return True

        return False


Migrator().run()


class Stats(BaseModel):  # pragma: no cover
    trade_symbol: str

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._name = datetime.today().date().strftime("%Y-%m-%d")

    @computed_field
    def volume(self) -> float | None:
        try:
            result = float(redis.hget(self._name, f"{self.trade_symbol}_VOLUME"))
        except TypeError:
            return None
        return result

    @computed_field
    def volume_trades(self) -> tuple[float, float] | None:
        pipe = redis.pipeline()
        pipe.hget(self._name, f"{self.trade_symbol}_VOLUME_BUY_ORDERS")
        pipe.hget(self._name, f"{self.trade_symbol}_VOLUME_SELL_ORDERS")
        result = pipe.execute()
        try:
            result = float(result[0]), float(result[1])
        except TypeError:
            return None
        return result

    @computed_field
    def number_trades(self) -> tuple[int, int] | None:
        pipe = redis.pipeline()
        pipe.hget(self._name, f"{self.trade_symbol}_NUMBER_BUY_ORDERS")
        pipe.hget(self._name, f"{self.trade_symbol}_NUMBER_SELL_ORDERS")
        result = pipe.execute()
        try:
            result = int(result[0]), int(result[1])
        except TypeError:
            return None
        return result


class History(BaseModel):  # pragma: no cover
    trade_symbol: str

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_date = datetime.today().date()

    @computed_field
    def rows(self) -> list[str]:
        cached_days = (
            (
                (self._current_date - timedelta(days=i)).strftime("%Y-%m-%d"),
                (self._current_date - timedelta(days=i)).strftime("%A")[:3],
            )
            for i in range(settings.REDIS_EXPIRATION)
        )

        data = []
        for name, dow in cached_days:
            with redis.pipeline() as pipe:
                pipe.hget(name, f"{self.trade_symbol}_VOLUME")
                pipe.hget(name, f"{self.trade_symbol}_VOLUME_BUY_ORDERS")
                pipe.hget(name, f"{self.trade_symbol}_VOLUME_SELL_ORDERS")
                pipe.hget(name, f"{self.trade_symbol}_NUMBER_BUY_ORDERS")
                pipe.hget(name, f"{self.trade_symbol}_NUMBER_SELL_ORDERS")
                pipe.hget(name, f"{self.trade_symbol}_PRICE")
                pipe.hget(name, f"{self.trade_symbol}_CURRENCY")
                pipe.hget(name, f"{self.trade_symbol}_EXCHANGES")
                result = pipe.execute()
            try:
                (
                    volume,
                    volume_buy_orders,
                    volume_sell_orders,
                    number_buy_orders,
                    number_sell_orders,
                    price_open,
                    currency,
                    exchanges,
                ) = (
                    float(result[0]),
                    float(result[1]),
                    float(result[2]),
                    int(result[3]),
                    int(result[4]),
                    float(result[5]),
                    result[6] or "-",
                    result[7] or "-",
                )
            except TypeError:
                break
            else:
                row = (
                    f"{name} | "
                    f"{dow} | "
                    f"{self.trade_symbol.ljust(4)} | "
                    f"{'{:,.2f} {}'.format(volume, self.trade_symbol.rjust(4)).rjust(21 + 5, ' ')} | "
                    f"{'{:,.2f} {}'.format(volume_buy_orders, self.trade_symbol.rjust(4)).rjust(21 + 5, ' ')} | "
                    f"{'{:,.2f} {}'.format(volume_sell_orders, self.trade_symbol.rjust(4)).rjust(21 + 5, ' ')} | "
                    f"{'{:,}'.format(number_buy_orders).rjust(14)} | "
                    f"{'{:,}'.format(number_sell_orders).rjust(15)} |"
                    f"{'{:,.8f} {}'.format(price_open, currency.rjust(4)).rjust(16 + 5, ' ')} | "
                    f"{exchanges}"
                )
                data.append(row)

        return data


class Status(BaseModel):  # pragma: no cover
    @computed_field
    def exchanges(self) -> dict[str, bool]:
        with redis.pipeline() as pipe:
            for exchange in settings.EXCHANGES:
                pipe.get(f"LAST_TS_{exchange.upper()}")
            result = pipe.execute()

        ret = {}
        for i, exchange in enumerate(settings.EXCHANGES):
            try:
                ret[exchange] = time.time() < (float(result[i]) + settings.EXCHANGES_STATUS_TTL)
            except TypeError:
                ret[exchange] = False

        return ret
