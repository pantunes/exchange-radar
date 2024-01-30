import asyncio
import logging

from pymexc import spot

from exchange_radar.producer.publisher import publish
from exchange_radar.producer.serializers.mexc import MexcTradeSerializer
from exchange_radar.producer.tasks.base import Task

logger = logging.getLogger(__name__)


ITER_SLEEP = 10.0


class MexcTradesTask(Task):
    async def process(self, symbol_or_symbols: str | tuple):
        def callback(message):
            try:
                for msg in message["d"]["deals"]:
                    msg.update({"s": message["s"]})
                    data = MexcTradeSerializer(**msg)
                    publish(data)
            except Exception as error:
                logger.error(f"ERROR: {error}")

        ws = spot.WebSocket()
        ws.deals_stream(callback, symbol_or_symbols)

        while True:
            await asyncio.sleep(ITER_SLEEP)
