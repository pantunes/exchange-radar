import asyncio
import logging
from typing import override

from pymexc import spot

from exchange_radar.producer.publisher import publish
from exchange_radar.producer.serializers.mexc import MexcTradeSerializer
from exchange_radar.producer.tasks.base import Task

logger = logging.getLogger(__name__)

logging.getLogger("pymexc.base_websocket").setLevel(logging.ERROR)


class MexcTradesTask(Task):
    @override
    async def task(self, symbols: tuple[str]):
        await asyncio.gather(self.process(symbols))

    @override
    async def process(self, symbol_or_symbols):
        while True:
            try:
                await self._start(symbol_or_symbols)
            except Exception as e:
                logger.error(f"WebSocket crashed: {e}, restarting in 5s...")
                await asyncio.sleep(5)

    async def _start(self, symbols):
        ws = spot.WebSocket(proto=True)

        def callback(message):
            try:
                if not hasattr(message, "publicAggreDeals"):
                    logger.warning(f"Malformed message: {message!r}")
                    return
                for deal in message.publicAggreDeals.deals:
                    trade_dict = {
                        "s": message.symbol,
                        "p": deal.price,
                        "v": deal.quantity,
                        "t": deal.time,
                        "S": deal.tradeType,
                    }
                    publish(MexcTradeSerializer(**trade_dict))
            except Exception as e:
                logger.error(f"Callback error: {e}")

        ws.deals_stream(callback, list(symbols), interval="10ms")

        while True:
            await asyncio.sleep(self.ITER_SLEEP)
