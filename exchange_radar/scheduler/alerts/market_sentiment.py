import logging
from collections import defaultdict
from datetime import datetime

from huey import crontab

from exchange_radar.scheduler.main import huey, redis
from exchange_radar.scheduler.settings.base import COINS, REDIS_EXPIRATION
from exchange_radar.web.src.models import Alerts

logger = logging.getLogger(__name__)

alerts_cache = defaultdict(dict)

INCREASE_IN_PERCENTAGE = 4.0


def _get_message(coin: str, currency: str, *, indicator: dict[str, int | float]) -> str | None:
    key, value = next(iter(indicator.items()))

    alerts_cache_coin = alerts_cache[coin]

    if alerts_cache_coin["currency"] != currency:
        logger.info(f"Mismatch in Currency: {alerts_cache_coin["currency"]} != {currency} for {coin}.")
        return None

    ratio = ((value / alerts_cache_coin[key]) - 1) * 100
    ratio_abs = abs(ratio)

    if ratio_abs < INCREASE_IN_PERCENTAGE:
        logger.info(f"No new {key.upper()} Alerts for {coin}. Ratio is {ratio}.")
        return None

    verb = "increased" if ratio > 0 else "decreased"
    return f"The {key.upper()} {verb} {ratio_abs:.2f}%"


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
            pipe.hget(name, f"{coin}_CURRENCY")
            pipe.hget("PRICE", coin)
            result = pipe.execute()
            try:
                (
                    volume,
                    volume_buy_orders,
                    volume_sell_orders,
                    number_buy_orders,
                    number_sell_orders,
                    currency,
                    price,
                ) = (
                    float(result[0]),
                    float(result[1]),
                    float(result[2]),
                    int(result[3]),
                    int(result[4]),
                    result[5],
                    float(result[6]),
                )
            except TypeError as error:
                logger.error(f"Error when parsing {coin} dataset: {error}")
                break
            else:
                if coin in alerts_cache:

                    messages = []

                    for indicator in (
                        {"volume": volume},
                        {"price": price},
                    ):
                        message = _get_message(coin, currency, indicator=indicator)
                        if message:
                            logger.info(message)
                            messages.append(message)

                    time_ts = int(datetime.now().timestamp())

                    for message in messages:
                        Alerts(
                            time_ts=time_ts,
                            trade_symbol=coin,
                            price=price,
                            currency=currency,
                            message=message,
                        ).save().expire(60 * 60 * 24 * REDIS_EXPIRATION)

                else:
                    logger.info("Initializing Alerts...")

                alerts_cache[coin] = {
                    "volume": volume,
                    "volume_buy_orders": volume_buy_orders,
                    "volume_sell_orders": volume_sell_orders,
                    "number_buy_orders": number_buy_orders,
                    "number_sell_orders": number_sell_orders,
                    "price": price,
                    "currency": currency,
                }

                logger.info(alerts_cache)
