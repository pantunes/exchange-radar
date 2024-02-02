import asyncio
import logging
from collections.abc import Callable

from kucoin.asyncio import KucoinSocketManager
from kucoin.client import Client

from exchange_radar.producer.publisher import publish
from exchange_radar.producer.serializers.kucoin import KucoinTradeSerializer
from exchange_radar.producer.tasks.base import Task

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)


ITER_SLEEP = 10.0


class KuCoinTradesTask(Task):
    def __init__(self):
        super().__init__()
        self.num_events = 0

    async def _subscribe(self, callback: Callable, symbol_or_symbols: str) -> KucoinSocketManager:
        async_client = Client("", "", "")
        kucoin_manager = await KucoinSocketManager.create(self.loop, async_client, callback)
        return await kucoin_manager.subscribe(f"/market/match:{symbol_or_symbols}")

    async def task(self, symbols: tuple[str]):
        await asyncio.gather(self.process(",".join(symbols)))

    async def process(self, symbol_or_symbols: str | tuple):
        try:

            async def callback(res):
                self.num_events = 0

                try:
                    data = KucoinTradeSerializer(**res["data"])
                    publish(data)
                except Exception as error:
                    logger.error(f"ERROR: {error}")

            kucoin_manager = await self._subscribe(callback, symbol_or_symbols)

            while True:
                self.num_events += 1

                if self.num_events <= 2:
                    logger.info(f"Trying again in {ITER_SLEEP} seconds...")
                    await asyncio.sleep(ITER_SLEEP)
                    continue

                try:
                    try:
                        logger.error("Unsubscribing...")
                        await kucoin_manager.unsubscribe(f"/market/match:{symbol_or_symbols}")
                    except Exception:
                        pass  # possibly nothing to unsubscribe

                    # re-subscribe
                    kucoin_manager = await self._subscribe(callback, symbol_or_symbols)

                    self.num_events = 0
                except Exception:
                    pass

        except Exception as error2:
            logger.error(f"GENERAL ERROR: {error2}")
