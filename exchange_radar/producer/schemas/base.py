from datetime import datetime
from decimal import Decimal, localcontext
from functools import cached_property

from pydantic import BaseModel, computed_field, field_validator

from exchange_radar.producer.settings.base import CURRENCIES


class CustomBaseModel(BaseModel):
    @computed_field
    @cached_property
    def total(self) -> Decimal:
        with localcontext() as ctx:
            ctx.prec = 14
            return self.price * self.quantity  # noqa

    @computed_field
    @cached_property
    def currency(self) -> str:
        for c in CURRENCIES:
            if c == self.symbol[-len(c) :]:  # noqa
                return c

        raise ValueError("Undefined currency")

    @computed_field
    @cached_property
    def trade_symbol(self) -> str:
        return self.symbol.replace(self.currency, "")  # noqa

    @field_validator("trade_time", mode="after", check_fields=False)
    def trade_time_after(cls, v) -> datetime:
        return v.replace(microsecond=0)

    @computed_field
    @cached_property
    def message(self) -> str:
        return (
            f"{self.trade_time} | "  # noqa
            f"<span class='{self.exchange.lower()}'>{self.exchange.ljust(8, ' ')}</span> | "  # noqa
            f"{'{:.8f} {}'.format(self.price, self.currency.rjust(4)).rjust(14 + 5, ' ')} | "  # noqa
            f"{'{:.8f} {}'.format(self.quantity, self.trade_symbol).rjust(21 + 5, ' ')} | "  # noqa
            f"{'{:.8f} {}'.format(self.total, self.currency.rjust(4)).rjust(17 + 5, ' ')}"  # noqa
        )

    @computed_field
    @cached_property
    def message_with_keys(self) -> str:
        return (
            f"{self.trade_time} | "  # noqa
            f"{self.exchange.ljust(8, ' ')} | "  # noqa
            f"{'PRICE: {:.8f} {}'.format(self.price, self.currency).rjust(7 + 14 + 5, ' ')} | "  # noqa
            f"{'QTY: {:.8f} {}'.format(self.quantity, self.trade_symbol).rjust(5 + 21 + 5, ' ')} | "  # noqa
            f"{'TOTAL: {:.8f} {}'.format(self.total, self.currency).rjust(7 + 17 + 5, ' ')}"  # noqa
        )
