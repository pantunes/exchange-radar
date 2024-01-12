from collections import defaultdict

from redis_om import Field, JsonModel, Migrator, get_redis_connection

from exchange_radar.web.src.settings import base as settings

redis = get_redis_connection()

cache_pks = defaultdict(list)


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
    def save_or_not(cls, coin: str, category: str, message: dict) -> bool:
        if coin in ("LTO",) or category in (
            "FeedWhales",
            "FeedDolphins",
        ):
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

            cache_pks[f"{coin}-{category}"].append(obj.pk)
            # print(f"CACHE_PKS: {cache_pks}")

            count = cls.find(
                (Feed.trade_symbol == coin) & (Feed.type == category)
            ).count()
            # print(f"COUNT: {count}")

            if count > settings.REDIS_MAX_ROWS:
                obj2del = cache_pks[f"{coin}-{category}"].pop(0)
                cls.delete(obj2del)
                # print(f"DELETE {coin}-{category}: {obj2del}")
                # count = cls.find(
                #     (Feed.trade_symbol == coin) & (Feed.type == category)
                # ).count()
                # print(f"POS-COUNT: {count}")

            return True

        return False


Migrator().run()
