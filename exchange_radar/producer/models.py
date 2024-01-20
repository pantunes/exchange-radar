from datetime import datetime, timedelta

from redis_om import get_redis_connection

from exchange_radar.producer.settings.base import REDIS_EXPIRATION

redis = get_redis_connection()


class RedisMixin:
    @staticmethod
    def _get_name() -> str:
        return datetime.today().date().strftime("%Y-%m-%d")

    def volume(self) -> float:
        return redis.hincrbyfloat(self._get_name(), f"{self.trade_symbol}_VOLUME", float(self.quantity))  # noqa

    def volume_trades(self) -> tuple[float, float] | None:
        name = self._get_name()

        with redis.pipeline() as pipe:
            pipe.expire(name=name, time=timedelta(days=REDIS_EXPIRATION), nx=True)

            if self.is_seller is False:  # noqa
                pipe.hincrbyfloat(
                    name,
                    f"{self.trade_symbol}_VOLUME_BUY_ORDERS",  # noqa
                    float(self.quantity),  # noqa
                )
                pipe.hget(name, f"{self.trade_symbol}_VOLUME_SELL_ORDERS")  # noqa
            else:
                pipe.hget(name, f"{self.trade_symbol}_VOLUME_BUY_ORDERS")  # noqa

                pipe.hincrbyfloat(
                    name,
                    f"{self.trade_symbol}_VOLUME_SELL_ORDERS",  # noqa
                    float(self.quantity),  # noqa
                )
            result = pipe.execute()

        try:
            result = float(result[1]), float(result[2])
        except TypeError:
            return None
        return result

    def number_trades(self) -> tuple[int, int] | None:
        name = self._get_name()

        with redis.pipeline() as pipe:
            pipe.expire(name=name, time=timedelta(days=REDIS_EXPIRATION), nx=True)

            if self.is_seller is False:  # noqa
                pipe.hincrby(name, f"{self.trade_symbol}_NUMBER_BUY_ORDERS", 1)  # noqa
                pipe.hget(name, f"{self.trade_symbol}_NUMBER_SELL_ORDERS")  # noqa
            else:
                pipe.hget(name, f"{self.trade_symbol}_NUMBER_BUY_ORDERS")  # noqa
                pipe.hincrby(name, f"{self.trade_symbol}_NUMBER_SELL_ORDERS", 1)  # noqa
            result = pipe.execute()

        try:
            result = int(result[1]), int(result[2])
        except TypeError:
            return None
        return result
