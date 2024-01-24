from datetime import datetime
from decimal import Decimal, localcontext
from functools import cached_property

from pydantic import BaseModel, computed_field, field_validator

from exchange_radar.producer.models import RedisMixin
from exchange_radar.producer.settings.base import CURRENCIES


class BaseSerializer(RedisMixin, BaseModel):
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
        return super().volume()

    @computed_field
    def volume_trades(self) -> tuple[float, float]:
        return super().volume_trades()

    @computed_field
    def number_trades(self) -> tuple[int, int]:
        return super().number_trades()

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
