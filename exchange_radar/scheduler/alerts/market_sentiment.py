from datetime import datetime

from huey import crontab

from exchange_radar.scheduler.main import huey, redis
from exchange_radar.scheduler.settings.base import COINS


@huey.periodic_task(crontab(minute="*/1"))
def bullish_or_bearish():
    name = datetime.today().date().strftime("%Y-%m-%d")

    with redis.pipeline() as pipe:
        for coin in COINS:
            pipe.hget(name, f"{coin}_VOLUME")
            pipe.hget(name, f"{coin}_VOLUME_BUY_ORDERS")
            pipe.hget(name, f"{coin}_VOLUME_SELL_ORDERS")
            pipe.hget(name, f"{coin}_NUMBER_BUY_ORDERS")
            pipe.hget(name, f"{coin}_NUMBER_SELL_ORDERS")
            pipe.hget(name, f"{coin}_PRICE")
            pipe.hget(name, f"{coin}_CURRENCY")
            pipe.hget(name, f"{coin}_EXCHANGES")
            result = pipe.execute()
            try:
                (
                    volume,
                    volume_buy_orders,
                    volume_sell_orders,
                    number_buy_orders,
                    number_sell_orders,
                    price,
                    currency,
                    exchanges,
                ) = (
                    float(result[0]),
                    float(result[1]),
                    float(result[2]),
                    int(result[3]),
                    int(result[4]),
                    float(result[5]),
                    result[6],
                    result[7],
                )
            except TypeError:
                break
            else:
                if volume_buy_orders > volume_sell_orders:
                    print("=" * 100)
                    print("*" * 100)
                    print(f"COIN: {coin}")
                    print("*" * 100)
                    print(f"VOLUME: {volume}")
                    print(f"VOLUME BUY ORDERS: {volume_buy_orders}")
                    print(f"VOLUME SELL ORDERS: {volume_sell_orders}")
                    print(f"NUMBER BUY ORDERS: {number_buy_orders}")
                    print(f"NUMBER SELL ORDERS: {number_sell_orders}")
                    print(f"PRICE: {price}")
                    print(f"RATIO: {(((volume_buy_orders / volume_sell_orders) - 1) * 100)}")
                    print("=" * 100)
                    print(f"CURRENCY: {currency}")
                    print(f"EXCHANGES: {exchanges}")
