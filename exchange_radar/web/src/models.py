import logging

from redis_om import Field, JsonModel, Migrator, get_redis_connection

from exchange_radar.web.src.settings import base as settings
from exchange_radar.web.src.types import ERdefaultdict

logger = logging.getLogger(__name__)


redis = get_redis_connection()

cache_pks = ERdefaultdict(list)


class Feed(JsonModel):
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
        "message_with_keys": "2024-01-10 22:37:02 | Binance  |  PRICE: 2549.83000000 USDT | ....."
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
    def select_rows(cls, coin: str, category: str) -> list[dict[str]]:
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
