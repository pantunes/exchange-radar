import logging
import time
from datetime import datetime, timedelta

from pydantic import BaseModel, computed_field
from redis_om import Field, JsonModel, Migrator, get_redis_connection

from exchange_radar.web.src.enums import Ranking
from exchange_radar.web.src.settings import base as settings

logger = logging.getLogger(__name__)

redis = get_redis_connection()

FEED_EXPIRATION_SECONDS = 60 * 60 * 24 * settings.REDIS_EXPIRATION
FEED_TRIM_BATCH = 1000


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
        "message": "2024-01-10 22:37:02 | <span class='binance'>Binance </span> |  2549.83000000 USDT | .....",
        "exchange": "Binance",
        "ranking": "Whale"
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
        "message": "2024-01-10 22:37:02 | <span class='binance'>Binance </span> |  2549.83000000 USDT | .....",
        "ranking": "Whale"
    }
    """

    type: str = Field(index=True)
    price: float
    trade_time_ts: int = Field(index=True, sortable=True)
    is_seller: bool
    currency: str
    trade_symbol: str = Field(index=True)
    volume: float
    # Producers send null until both buy and sell statistics exist for the day.
    volume_trades: list[float] | None = None
    number_trades: list[int] | None = None
    message: str
    ranking: Ranking

    class Config:
        use_enum_values = True

    @classmethod
    def is_coin_selected(cls, coin: str, category: str) -> bool:
        return category in (
            "FeedWhales",
            "FeedDolphins",
            "FeedOctopuses",
        )

    @classmethod
    def select_rows(cls, coin: str, category: str, limit: int | None = None) -> list[dict[str, str]]:
        # execute(exhaust_results=False) runs a single search; page() keeps paginating past the limit.
        return [
            item.dict()
            for item in cls.find((cls.trade_symbol == coin) & (cls.type == category))
            .sort_by("-trade_time_ts")
            .copy(offset=0, limit=settings.REDIS_MAX_ROWS if limit is None else limit)
            .execute(exhaust_results=False)
        ][::-1]

    @classmethod
    def trim(cls, coin: str, category: str) -> int:
        """Delete up to FEED_TRIM_BATCH rows beyond the retained history, using one search."""
        query = cls.find((cls.trade_symbol == coin) & (cls.type == category)).query
        _, *keys = redis.execute_command(
            "FT.SEARCH",
            cls.Meta.index_name,
            query,
            "NOCONTENT",
            "SORTBY",
            "trade_time_ts",
            "DESC",
            "LIMIT",
            settings.FEED_RETENTION_ROWS,
            FEED_TRIM_BATCH,
        )
        if not keys:
            return 0

        num_deleted = redis.delete(*keys)
        logger.info(f"TRIM {coin} {category}: {num_deleted} rows deleted")
        return num_deleted

    @classmethod
    def save_or_not(cls, coin: str, category: str, message: dict) -> bool:
        if not cls.is_coin_selected(coin, category):
            return False

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
            ranking=message["ranking"],
        )
        with redis.pipeline(transaction=False) as pipe:
            obj.save(pipeline=pipe)
            obj.expire(num_seconds=FEED_EXPIRATION_SECONDS, pipeline=pipe)
            pipe.execute()

        cls.trim(coin=coin, category=category)

        return True


class Alerts(JsonModel):  # pragma: no cover
    name: str
    time_ts: int = Field(index=True, sortable=True)
    trade_symbol: str = Field(index=True)
    price: float
    currency: str
    message: str

    @classmethod
    def rows(cls, trade_symbol: str) -> dict[str, list[str]]:
        query = cls.find(cls.trade_symbol == trade_symbol).sort_by("-time_ts")
        return {
            "rows": [
                f"{datetime.fromtimestamp(item.time_ts)} | "
                f"{trade_symbol.ljust(4)} | "
                f"{f'{item.price:,.8f} {item.currency.rjust(4)}'.rjust(16 + 5, ' ')} | "
                f"{item.name.ljust(35)} | "
                f"{item.message}"
                for item in query
            ]
        }


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
        with redis.pipeline() as pipe:
            for name, dow in cached_days:
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
                        f"{f'{volume:,.2f} {self.trade_symbol.rjust(4)}'.rjust(21 + 5, ' ')} | "
                        f"<span class='{'order_buy' if volume_buy_orders > volume_sell_orders else 'order_sell'}'>"
                        f"{f'{volume_buy_orders:,.2f} {self.trade_symbol.rjust(4)}'.rjust(21 + 5, ' ')} | "
                        f"{f'{volume_sell_orders:,.2f} {self.trade_symbol.rjust(4)}'.rjust(21 + 5, ' ')} "
                        f"| </span>"
                        f"<span class='{'order_buy' if number_buy_orders > number_sell_orders else 'order_sell'}'>"
                        f"{f'{number_buy_orders:,}'.rjust(14)} | "
                        f"{f'{number_sell_orders:,}'.rjust(15)} | </span>"
                        f"{f'{price_open:,.8f} {currency.rjust(4)}'.rjust(16 + 5, ' ')} | "
                        f"{exchanges}"
                    )
                    data.append(row)

        return data


class Status(BaseModel):  # pragma: no cover
    @computed_field
    def exchanges(self) -> dict[str, bool]:
        with redis.pipeline() as pipe:
            for exchange in settings.EXCHANGES:
                pipe.hget("EXCHANGES", exchange.upper())
            result = pipe.execute()

        ret = {}
        for i, exchange in enumerate(settings.EXCHANGES):
            try:
                ret[exchange] = time.time() < (float(result[i]) + settings.EXCHANGES_STATUS_TTL)
            except TypeError:
                ret[exchange] = False

        return ret
