import asyncio
import json
import logging
from collections.abc import Callable

from okx.websocket.WsPublicAsync import WsPublicAsync

from exchange_radar.producer.publisher import publish
from exchange_radar.producer.serializers.okx import OkxTradeSerializer
from exchange_radar.producer.tasks.base import Task

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

logging.getLogger("WsPublic").propagate = False


ITER_SLEEP = 10.0


class OkxTradesTask(Task):
    def __init__(self):
        super().__init__()
        self.num_events = 0

    @staticmethod
    async def _subscribe(ws, callback: Callable, symbols: list):
        await ws.start()
        await ws.subscribe(symbols, callback)

    async def task(self, symbols: tuple[dict]):
        await asyncio.gather(self.process(tuple([{"channel": "trades-all", "instId": symbol} for symbol in symbols])))

    async def process(self, symbol_or_symbols: str | tuple):
        url = "wss://ws.okx.com:8443/ws/v5/business"

        try:

            def callback(message):
                self.num_events = 0

                try:
                    for msg in json.loads(message)["data"]:
                        data = OkxTradeSerializer(**msg)
                        publish(data)
                except Exception as error:
                    logger.error(f"ERROR: {error}")

            _symbols = list(symbol_or_symbols)

            ws = WsPublicAsync(url=url)
            await self._subscribe(ws=ws, callback=callback, symbols=_symbols)

            while True:
                self.num_events += 1

                if self.num_events <= 2:
                    logger.info(f"Trying again in {ITER_SLEEP} seconds...")
                    await asyncio.sleep(ITER_SLEEP)
                    continue

                try:
                    try:
                        logger.error("Unsubscribing...")
                        await ws.unsubscribe(_symbols, callback)
                    except Exception:
                        pass  # possibly nothing to unsubscribe

                    # re-subscribe
                    ws = WsPublicAsync(url=url)
                    await self._subscribe(ws=ws, callback=callback, symbols=_symbols)

                    self.num_events = 0
                except Exception:
                    pass

        except Exception as error2:
            logger.error(f"GENERAL ERROR: {error2}")
