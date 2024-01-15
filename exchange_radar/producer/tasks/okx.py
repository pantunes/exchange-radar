import asyncio
import json
import logging

from okx.websocket.WsPublicAsync import WsPublicAsync

from exchange_radar.producer.publisher import publish
from exchange_radar.producer.serializers.okx import OkxTradeSerializer
from exchange_radar.producer.task import Task

logger = logging.getLogger(__name__)

logging.getLogger("WsPublic").propagate = False


ITER_SLEEP = 10.0


class OkxTradesTask(Task):
    async def task(self, symbols: tuple[str]):
        await asyncio.gather(self.process(symbols))

    async def process(self, symbol_or_symbols: str | tuple):
        def callback(message):
            try:
                data = OkxTradeSerializer(**json.loads(message)["data"][0])
                publish(data)
            except Exception as error:
                logger.error(f'GENERAL ERROR: "{error}"; MESSAGE {message}')

        ws = WsPublicAsync(url="wss://ws.okx.com:8443/ws/v5/business")
        await ws.start()
        await ws.subscribe([{"channel": "trades-all", "instId": symbol} for symbol in symbol_or_symbols], callback)

        while True:
            await asyncio.sleep(ITER_SLEEP)
