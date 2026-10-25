import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from math import isfinite

from huey import crontab

from exchange_radar.scheduler.main import huey, redis
from exchange_radar.scheduler.settings.base import COINS, REDIS_EXPIRATION
from exchange_radar.web.src.models import Alerts

logger = logging.getLogger(__name__)

alerts_cache: defaultdict[str, defaultdict[str, dict]] = defaultdict(lambda: defaultdict(dict))


TASK_LOCK = "MARKET-SENTIMENT-LOCK"


class TaskConfig(ABC):
    @property
    def name(self) -> str:
        return f"Price change ≥{self.price_percentage_change:g}% · {self.frequency_in_minutes} min · up/down"

    @property
    @abstractmethod
    def price_percentage_change(self) -> float: ...

    @property
    @abstractmethod
    def frequency_in_minutes(self) -> int: ...

    def __str__(self) -> str:
        return self.__class__.__name__


class EachMinuteTaskConfig(TaskConfig):
    price_percentage_change = 1.0
    frequency_in_minutes = 1


class Each10MinutesTaskConfig(TaskConfig):
    price_percentage_change = 2.0
    frequency_in_minutes = 10


def _format_elapsed(seconds: int) -> str:
    parts = []
    for unit, unit_seconds in (("hour", 3600), ("min", 60), ("sec", 1)):
        value, seconds = divmod(max(0, seconds), unit_seconds)
        if value:
            parts.append(f"{value} {unit}{'s' if value != 1 else ''}")
    return " ".join(parts) or "0 secs"


def _get_message(
    key: str,
    coin: str,
    currency: str,
    price_percentage_change: float,
    frequency_in_minutes: int,
    *,
    time_ts: int,
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
    elapsed = _format_elapsed(time_ts - alerts_cache_coin["time_ts"])
    return f"{indicator_key.capitalize()} {verb} {ratio_abs:.2f}% over {elapsed}."


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
    key = f"{name} {config}"

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
                if not currency or not isfinite(price) or price <= 0:
                    raise ValueError("price must be positive and finite, and currency must be present")
            except (TypeError, ValueError) as error:
                # A gap invalidates this coin's comparison interval, not the other coins' alerts.
                alerts_cache.get(key, {}).pop(coin, None)
                logger.warning("Skipping alerts for %s: missing or invalid statistics (%s)", coin, error)
                continue
            else:
                time_ts = int(datetime.now().timestamp())
                if key in alerts_cache and coin in alerts_cache[key]:

                    messages = []

                    for indicator in ({"price": price},):
                        message = _get_message(
                            key,
                            coin,
                            currency,
                            config.price_percentage_change,
                            config.frequency_in_minutes,
                            time_ts=time_ts,
                            indicator=indicator,
                        )
                        if message:
                            logger.info(message)
                            messages.append(message)

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
                    "time_ts": time_ts,
                    "volume": volume,
                    "volume_buy_orders": volume_buy_orders,
                    "volume_sell_orders": volume_sell_orders,
                    "number_buy_orders": number_buy_orders,
                    "number_sell_orders": number_sell_orders,
                    "price": price,
                    "currency": currency,
                }

                logger.info(alerts_cache)
