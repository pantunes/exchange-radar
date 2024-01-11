from datetime import datetime

from pydantic import BaseModel, computed_field
from redis_om import get_redis_connection

redis = get_redis_connection()


class StatsSerializer(BaseModel):
    trade_symbol: str

    @computed_field
    def volume(self) -> float:
        today_date = datetime.today().date().strftime("%Y-%m-%d")
        return float(redis.hget(today_date, f"{self.trade_symbol}_VOLUME"))

    @computed_field
    def volume_trades(self) -> tuple[float, float]:
        today_date = datetime.today().date().strftime("%Y-%m-%d")

        vol_trades_buy_orders = float(
            redis.hget(today_date, f"{self.trade_symbol}_VOLUME_TRADES_BUY_ORDERS")
        )
        vol_trades_sell_orders = float(
            redis.hget(today_date, f"{self.trade_symbol}_VOLUME_TRADES_SELL_ORDERS")
        )
        return vol_trades_buy_orders, vol_trades_sell_orders

    @computed_field
    def number_trades(self) -> tuple[int, int]:
        today_date = datetime.today().date().strftime("%Y-%m-%d")

        num_trades_buy_orders = int(
            redis.hget(today_date, f"{self.trade_symbol}_NUMBER_TRADES_BUY_ORDERS")
        )
        num_trades_sell_orders = int(
            redis.hget(today_date, f"{self.trade_symbol}_NUMBER_TRADES_SELL_ORDERS")
        )
        return num_trades_buy_orders, num_trades_sell_orders
