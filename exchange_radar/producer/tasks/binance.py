import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from time import monotonic
from typing import override

from binance import AsyncClient, BinanceSocketManager, exceptions

from exchange_radar.producer.batching import TradeBatch, TradeStatsStore
from exchange_radar.producer.tasks.base import Task

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class BinanceTradesTask(Task):
    MAX_RETRY_DELAY = 60.0
    SOCKET_QUEUE_SIZE = 5000
    BATCH_SIZE = 50
    BATCH_WAIT = 0.02
    MAX_PENDING_TRADES = 5000

    def __init__(self):
        super().__init__()
        self._pending = asyncio.Queue(maxsize=self.MAX_PENDING_TRADES)
        self._received = 0
        # Pika's blocking connection remains confined to a single worker thread.
        self._publisher_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="binance-publisher")

    @override
    async def task(self, symbols: tuple[str, ...]):
        try:
            async with asyncio.TaskGroup() as group:
                group.create_task(self._publish_batches())
                for symbol in symbols:
                    group.create_task(self.process(symbol))
        finally:
            self._publisher_executor.shutdown(wait=True, cancel_futures=True)

    async def _publish_batches(self):
        loop = asyncio.get_running_loop()
        store = TradeStatsStore()
        processed = 0
        last_report = loop.time()
        while True:
            items = [await self._pending.get()]
            try:
                deadline = loop.time() + self.BATCH_WAIT
                while len(items) < self.BATCH_SIZE:
                    try:
                        items.append(self._pending.get_nowait())
                    except asyncio.QueueEmpty:
                        remaining = deadline - loop.time()
                        if remaining <= 0:
                            break
                        try:
                            items.append(await asyncio.wait_for(self._pending.get(), remaining))
                        except TimeoutError:
                            break

                batch = await loop.run_in_executor(
                    self._publisher_executor, TradeBatch, [message for _, message in items]
                )
                retry_delay = 1.0
                while True:
                    try:
                        await loop.run_in_executor(self._publisher_executor, batch.process, store)
                        break
                    except Exception:
                        logger.exception("Binance batch failed; retrying in %s seconds", retry_delay)
                        await asyncio.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 10.0)

                processed += len(items)
                if loop.time() - last_report >= 60:
                    logger.info(
                        "Binance throughput: received=%s processed=%s queued=%s oldest_batch_age=%.3fs",
                        self._received,
                        processed,
                        self._pending.qsize(),
                        loop.time() - items[0][0],
                    )
                    last_report = loop.time()
            finally:
                for _ in items:
                    self._pending.task_done()

    @override
    async def process(self, symbol_or_symbols: str | tuple):
        retry_delay = self.ITER_SLEEP
        while True:
            async_client = None
            connected_at = None
            try:
                async_client = await AsyncClient.create()
                # The SDK must absorb a network burst before our reader gets a turn.
                binance_manager = BinanceSocketManager(async_client, max_queue_size=self.SOCKET_QUEUE_SIZE)
                async with binance_manager.trade_socket(symbol_or_symbols) as ts:
                    connected_at = monotonic()
                    while True:
                        message = await ts.recv()
                        if message.get("e") == "error":
                            raise exceptions.BinanceWebsocketClosed(message.get("m", "Binance websocket error"))
                        await self._pending.put((asyncio.get_running_loop().time(), message))
                        self._received += 1
            except Exception as error:
                if connected_at is not None and monotonic() - connected_at >= self.MAX_RETRY_DELAY:
                    retry_delay = self.ITER_SLEEP
                logger.warning(
                    "Binance stream %s failed: %s. Reconnecting in %s seconds...",
                    symbol_or_symbols,
                    error,
                    retry_delay,
                )
            finally:
                if async_client is not None:
                    try:
                        await async_client.close_connection()
                    except Exception:
                        logger.exception("Failed to close Binance client for %s", symbol_or_symbols)

            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, self.MAX_RETRY_DELAY)
