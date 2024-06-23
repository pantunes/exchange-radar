import asyncio
import logging
import sys
from typing import override

from pymexc import spot

from exchange_radar.producer.publisher import publish
from exchange_radar.producer.serializers.mexc import MexcTradeSerializer
from exchange_radar.producer.tasks.base import Task

logger = logging.getLogger(__name__)


class MexcTradesTask(Task):
    @override
    async def task(self, symbols: tuple[str]):
        await asyncio.gather(self.process(symbols))

    @override
    async def process(self, symbol_or_symbols: str | tuple):
        def callback(message):
            try:
                for msg in message["d"]["deals"]:
                    msg.update({"s": message["s"]})
                    data = MexcTradeSerializer(**msg)
                    publish(data)
            except Exception as error:
                logger.error(f"ERROR: {error}")

        try:
            ws = spot.WebSocket()
            ws._ws_subscribe("public.deals", callback, [{"symbol": symbol} for symbol in symbol_or_symbols])

            while True:
                await asyncio.sleep(self.ITER_SLEEP)

        except Exception as error2:
            logger.error(f"EXIT ERROR: {error2}")
            sys.exit(1)
