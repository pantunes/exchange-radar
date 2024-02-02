import asyncio
import logging

from pybit.unified_trading import WebSocket

from exchange_radar.producer.publisher import publish
from exchange_radar.producer.serializers.bybit import BybitTradeSerializer
from exchange_radar.producer.tasks.base import Task

logger = logging.getLogger(__name__)


ITER_SLEEP = 10.0


class BybitTradesTask(Task):
    async def task(self, symbols: tuple[str]):
        await asyncio.gather(self.process(symbols))

    async def process(self, symbol_or_symbols: str | tuple):
        def callback(message):
            try:
                for msg in message["data"]:
                    data = BybitTradeSerializer(**msg)
                    publish(data)
            except Exception as error:
                logger.error(f"ERROR: {error}")

        ws = WebSocket(
            testnet=False,
            channel_type="spot",
        )

        ws.trade_stream(symbol=symbol_or_symbols, callback=callback)

        while True:
            await asyncio.sleep(ITER_SLEEP)
