from datetime import datetime

from pydantic import BaseModel, computed_field
from redis_om import get_redis_connection

redis = get_redis_connection()


class StatsSerializer(BaseModel):
    trade_symbol: str

    @computed_field
    def volume(self) -> float | None:
        today_date = datetime.today().date().strftime("%Y-%m-%d")
        try:
            return float(redis.hget(today_date, f"{self.trade_symbol}_VOLUME"))
        except TypeError:
            pass

    @computed_field
    def volume_trades(self) -> tuple[float, float] | None:
        today_date = datetime.today().date().strftime("%Y-%m-%d")
        pipeline = redis.pipeline()
        pipeline.hget(today_date, f"{self.trade_symbol}_VOLUME_TRADES_BUY_ORDERS")
        pipeline.hget(today_date, f"{self.trade_symbol}_VOLUME_TRADES_SELL_ORDERS")
        result = pipeline.execute()
        try:
            return float(result[0]), float(result[1])
        except TypeError:
            pass

    @computed_field
    def number_trades(self) -> tuple[int, int] | None:
        today_date = datetime.today().date().strftime("%Y-%m-%d")
        pipeline = redis.pipeline()
        pipeline.hget(today_date, f"{self.trade_symbol}_NUMBER_TRADES_BUY_ORDERS")
        pipeline.hget(today_date, f"{self.trade_symbol}_NUMBER_TRADES_SELL_ORDERS")
        result = pipeline.execute()
        try:
            return int(result[0]), int(result[1])
        except TypeError:
            pass
