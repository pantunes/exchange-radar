from datetime import datetime
from decimal import Decimal, localcontext
from functools import cached_property

from pydantic import BaseModel, computed_field, field_validator
from redis_om import get_redis_connection

from exchange_radar.producer.settings.base import CURRENCIES

redis = get_redis_connection()


class BaseSerializer(BaseModel):
    @field_validator("trade_time", check_fields=False)  # noqa
    @classmethod
    def trade_time_normalization(cls, v) -> str:
        return v.replace(tzinfo=None)

    @computed_field
    @cached_property
    def total(self) -> Decimal:
        with localcontext() as ctx:
            ctx.prec = 14
            return self.price * self.quantity

    @computed_field
    @cached_property
    def currency(self) -> str:
        for c in CURRENCIES:
            if c == self.symbol[-len(c) :]:  # noqa: E203
                return c

        raise ValueError("Undefined currency")

    @computed_field
    @cached_property
    def trade_symbol(self) -> str:
        return self.symbol.replace(self.currency, "")

    @computed_field
    def volume(self) -> float:
        today_date = datetime.today().date().strftime("%Y-%m-%d")
        return redis.hincrbyfloat(today_date, f"{self.trade_symbol}_VOLUME", float(self.quantity))

    @computed_field
    def volume_trades(self) -> tuple[float, float]:
        today_date = datetime.today().date().strftime("%Y-%m-%d")
        pipeline = redis.pipeline()
        if self.is_seller is False:
            pipeline.hincrbyfloat(
                today_date,
                f"{self.trade_symbol}_VOLUME_TRADES_BUY_ORDERS",
                float(self.quantity),
            )
            pipeline.hget(today_date, f"{self.trade_symbol}_VOLUME_TRADES_SELL_ORDERS")
        else:
            pipeline.hget(today_date, f"{self.trade_symbol}_VOLUME_TRADES_BUY_ORDERS")
            pipeline.hincrbyfloat(
                today_date,
                f"{self.trade_symbol}_VOLUME_TRADES_SELL_ORDERS",
                float(self.quantity),
            )
        result = pipeline.execute()
        return float(result[0]), float(result[1])

    @computed_field
    def number_trades(self) -> tuple[int, int]:
        today_date = datetime.today().date().strftime("%Y-%m-%d")
        pipeline = redis.pipeline()
        if self.is_seller is False:
            pipeline.hincrby(today_date, f"{self.trade_symbol}_NUMBER_TRADES_BUY_ORDERS", 1)
            pipeline.hget(today_date, f"{self.trade_symbol}_NUMBER_TRADES_SELL_ORDERS")
        else:
            pipeline.hget(today_date, f"{self.trade_symbol}_NUMBER_TRADES_BUY_ORDERS")
            pipeline.hincrby(today_date, f"{self.trade_symbol}_NUMBER_TRADES_SELL_ORDERS", 1)
        result = pipeline.execute()
        return int(result[0]), int(result[1])

    @field_validator("trade_time", mode="after", check_fields=False)  # noqa
    @classmethod
    def trade_time_after(cls, v) -> datetime:
        return v.replace(microsecond=0)

    @computed_field
    @cached_property
    def trade_time_ts(self) -> int:
        return int(self.trade_time.timestamp())

    @computed_field
    @cached_property
    def message(self) -> str:
        return (
            f"{self.trade_time} | "
            f"<span class='{self.exchange.lower()}'>{self.exchange.ljust(8, ' ')}</span> | "
            f"{'{:.8f} {}'.format(self.price, self.currency.rjust(4)).rjust(14 + 5, ' ')} | "
            f"{'{:.8f} {}'.format(self.quantity, self.trade_symbol).rjust(21 + 5, ' ')} | "
            f"{'{:.8f} {}'.format(self.total, self.currency.rjust(4)).rjust(17 + 5, ' ')}"
        )

    @computed_field
    @cached_property
    def message_with_keys(self) -> str:
        return (
            f"{self.trade_time} | "
            f"{self.exchange.ljust(8, ' ')} | "
            f"{'PRICE: {:.8f} {}'.format(self.price, self.currency).rjust(7 + 14 + 5, ' ')} | "
            f"{'QTY: {:.8f} {}'.format(self.quantity, self.trade_symbol).rjust(5 + 21 + 5, ' ')} | "
            f"{'TOTAL: {:.8f} {}'.format(self.total, self.currency).rjust(7 + 17 + 5, ' ')}"
        )
