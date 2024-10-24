import asyncio
import logging
import sys
from typing import override

from pybit.unified_trading import WebSocket

from exchange_radar.producer.publisher import publish
from exchange_radar.producer.serializers.bybit import BybitTradeSerializer
from exchange_radar.producer.tasks.base import Task

logger = logging.getLogger(__name__)


class BybitTradesTask(Task):
    @override
    async def task(self, symbols: tuple[str]):
        await asyncio.gather(self.process(symbols))

    @override
    async def process(self, symbol_or_symbols: str | tuple):
        def callback(message):
            try:
                for msg in message["data"]:
                    data = BybitTradeSerializer(**msg)
                    publish(data)
            except Exception as error:
                logger.error(f"ERROR: {error}")

        try:
            ws = WebSocket(testnet=False, channel_type="spot")
            ws.trade_stream(symbol=symbol_or_symbols, callback=callback)

            while True:
                await asyncio.sleep(self.ITER_SLEEP)

        except Exception as error2:
            logger.error(f"EXIT ERROR: {error2}")
            sys.exit(1)
