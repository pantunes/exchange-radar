import json
import logging
import time
import uuid
from pathlib import Path

from exchange_radar.producer import models
from exchange_radar.producer.publisher import publish
from exchange_radar.producer.serializers.binance import BinanceTradeSerializer
from exchange_radar.producer.settings.base import REDIS_EXPIRATION
from exchange_radar.producer.utils import get_exchanges

logger = logging.getLogger(__name__)
SCRIPT = Path(__file__).with_name("trade_stats.lua").read_text()


def pair(first, second, convert):
    if first is None or second is None:
        return None
    return convert(first), convert(second)


class TradeStatsStore:
    def __init__(self, client=None):
        self.client = client if client is not None else models.redis
        self.script = self.client.register_script(SCRIPT)
        self.cache_key = f"trades:batch:{uuid.uuid4().hex}"

    def apply(self, trades, token=None):
        pending = [trade for trade in trades if trade._stats_snapshot is None and not trade._duplicate]
        if not pending:
            return

        keys = ["COINS", "EXCHANGES", self.cache_key]
        payload = []
        for trade in pending:
            day, seen = trade._name, f"trades:seen:{trade._name}"
            for key in (day, seen):
                if key not in keys:
                    keys.append(key)
            payload.append(
                {
                    "day": keys.index(day) + 1,
                    "seen": keys.index(seen) + 1,
                    "coin": trade.trade_symbol,
                    "symbol": trade.symbol,
                    "exchange": trade.exchange.upper(),
                    "currency": trade.currency,
                    "exchanges": get_exchanges(coin=trade.trade_symbol),
                    "quantity": str(float(trade.quantity)),
                    "price": str(float(trade.price)),
                    "seller": trade.is_seller,
                    "id": str(trade.trade_id) if getattr(trade, "trade_id", None) is not None else False,
                }
            )

        response = self.script(
            keys=keys,
            args=[json.dumps(payload), REDIS_EXPIRATION * 86400, time.time(), token or uuid.uuid4().hex],
        )
        for trade, snapshot in zip(pending, json.loads(response), strict=True):
            if snapshot is False:
                trade._duplicate = True
                continue
            volume, buy_volume, sell_volume, buy_count, sell_count = snapshot
            trade._stats_snapshot = {
                "volume": float(volume),
                "volume_trades": pair(buy_volume, sell_volume, float),
                "number_trades": pair(buy_count, sell_count, int),
            }


class TradeBatch:
    def __init__(self, messages, serializer=BinanceTradeSerializer):
        self.trades = []
        self.next_trade = 0
        self.token = uuid.uuid4().hex
        for message in messages:
            try:
                trade = serializer(_defer_stats=True, **message)
                # Validate computed metadata before any statistics are written.
                trade.currency, trade.trade_symbol, trade.ranking, trade.message
                self.trades.append(trade)
            except (ValueError, TypeError, KeyError, IndexError):
                logger.exception("Invalid %s trade: %s", serializer.__name__, message)

    def process(self, store):
        store.apply(self.trades, self.token)
        while self.next_trade < len(self.trades):
            trade = self.trades[self.next_trade]
            if not trade._duplicate:
                publish(trade, raise_on_error=True)
            self.next_trade += 1
