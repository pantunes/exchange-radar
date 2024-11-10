import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime

from huey import crontab

from exchange_radar.scheduler.main import huey, redis
from exchange_radar.scheduler.settings.base import COINS, REDIS_EXPIRATION
from exchange_radar.web.src.models import Alerts

logger = logging.getLogger(__name__)

alerts_cache: defaultdict[str, defaultdict[str, dict]] = defaultdict(lambda: defaultdict(dict))


TASK_LOCK = "MARKET-SENTIMENT-LOCK"


class TaskConfig(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def price_percentage_change(self) -> float: ...

    @property
    @abstractmethod
    def frequency_in_minutes(self) -> int: ...

    def __str__(self) -> str:
        return self.__class__.__name__


class EachMinuteTaskConfig(TaskConfig):
    name = "price-change-1-min"
    price_percentage_change = 1.0
    frequency_in_minutes = 1


class Each10MinutesTaskConfig(TaskConfig):
    name = "price-change-10-mins"
    price_percentage_change = 2.0
    frequency_in_minutes = 10


def _get_message(
    key: str,
    coin: str,
    currency: str,
    price_percentage_change: float,
    frequency_in_minutes: int,
    *,
    indicator: dict[str, int | float],
) -> str | None:
    indicator_key, indicator_value = next(iter(indicator.items()))

    alerts_cache_coin = alerts_cache[key][coin]

    if alerts_cache_coin["currency"] != currency:
        logger.info(f"Mismatch in Currency: {alerts_cache_coin['currency']} != {currency} for {coin}.")
        return None

    ratio = ((indicator_value / alerts_cache_coin[indicator_key]) - 1) * 100
    ratio_abs = abs(ratio)

    if ratio_abs < price_percentage_change:
        logger.info(
            f"No new {indicator_key.upper()} alerts for coin:{coin}; "
            f"frequency_in_minutes:{frequency_in_minutes} ratio: {ratio}."
        )
        return None

    verb = "increased" if ratio > 0 else "decreased"
    return f"The {indicator_key.upper()} {verb} {ratio_abs:.2f}% in the last {frequency_in_minutes} minute(s)"


@huey.periodic_task(crontab(minute="*/1"))
@huey.lock_task(TASK_LOCK)
def bullish_or_bearish__1_min():
    task(config=EachMinuteTaskConfig())


@huey.periodic_task(crontab(minute="*/10"))
@huey.lock_task(TASK_LOCK)
def bullish_or_bearish__10_min():
    task(config=Each10MinutesTaskConfig())


def task(*, config: TaskConfig):
    name = datetime.today().date().strftime("%Y-%m-%d")

    with redis.pipeline() as pipe:
        for coin in COINS:
            pipe.hget(name, f"{coin}_VOLUME")
            pipe.hget(name, f"{coin}_VOLUME_BUY_ORDERS")
            pipe.hget(name, f"{coin}_VOLUME_SELL_ORDERS")
            pipe.hget(name, f"{coin}_NUMBER_BUY_ORDERS")
            pipe.hget(name, f"{coin}_NUMBER_SELL_ORDERS")
            pipe.hget("COINS", f"{coin}_PRICE")
            pipe.hget("COINS", f"{coin}_CURRENCY")
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
                ) = (
                    float(result[0]),
                    float(result[1]),
                    float(result[2]),
                    int(result[3]),
                    int(result[4]),
                    float(result[5]),
                    result[6],
                )
            except TypeError as error:
                logger.error(f"Error when parsing {coin}: {error}")
                break
            else:
                key = f"{name} {config}"

                if key in alerts_cache and coin in alerts_cache[key]:

                    messages = []

                    for indicator in ({"price": price},):
                        message = _get_message(
                            key,
                            coin,
                            currency,
                            config.price_percentage_change,
                            config.frequency_in_minutes,
                            indicator=indicator,
                        )
                        if message:
                            logger.info(message)
                            messages.append(message)

                    time_ts = int(datetime.now().timestamp())

                    for message in messages:
                        Alerts(
                            name=config.name,
                            time_ts=time_ts,
                            trade_symbol=coin,
                            price=price,
                            currency=currency,
                            message=message,
                        ).save().expire(num_seconds=60 * 60 * 24 * REDIS_EXPIRATION)

                else:
                    logger.info("Initializing Alerts...")

                alerts_cache[key][coin] = {
                    "volume": volume,
                    "volume_buy_orders": volume_buy_orders,
                    "volume_sell_orders": volume_sell_orders,
                    "number_buy_orders": number_buy_orders,
                    "number_sell_orders": number_sell_orders,
                    "price": price,
                    "currency": currency,
                }

                logger.info(alerts_cache)
