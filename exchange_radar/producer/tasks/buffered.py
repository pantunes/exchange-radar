import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from time import monotonic

import websockets

from exchange_radar.producer.batching import TradeBatch, TradeStatsStore
from exchange_radar.producer.tasks.base import Task

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class BufferedTradesTask(Task):
    """Keep exchange readers responsive while a single thread publishes batches."""

    MAX_RETRY_DELAY = 60.0
    MAX_PENDING_TRADES = 5000
    BATCH_SIZE = 50
    BATCH_WAIT = 0.02
    REPORT_INTERVAL = 60.0
    RECEIVE_TIMEOUT = 30.0
    SEND_TIMEOUT = 10.0
    LOOP_CHECK_INTERVAL = 1.0
    LOOP_LAG_WARNING = 1.0

    def __init__(self):
        super().__init__()
        self._pending = asyncio.Queue(maxsize=self.MAX_PENDING_TRADES)
        self._received = 0
        self._peak_queue = 0
        self._loop_lag = 0.0
        self._publisher_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"{self.EXCHANGE}-publisher")

    def streams(self, symbols):
        return [tuple(symbols)]

    async def task(self, symbols):
        try:
            async with asyncio.TaskGroup() as group:
                group.create_task(self._publish_batches())
                group.create_task(self._monitor_loop())
                for stream in self.streams(symbols):
                    group.create_task(self.process(stream))
        finally:
            self._publisher_executor.shutdown(wait=True, cancel_futures=True)

    async def _monitor_loop(self):
        loop = asyncio.get_running_loop()
        while True:
            expected = loop.time() + self.LOOP_CHECK_INTERVAL
            await asyncio.sleep(self.LOOP_CHECK_INTERVAL)
            lag = max(0.0, loop.time() - expected)
            self._loop_lag = max(self._loop_lag, lag)
            if lag >= self.LOOP_LAG_WARNING:
                logger.warning("%s socket loop delayed by %.3fs", self.EXCHANGE, lag)

    def enqueue(self, messages):
        if not isinstance(messages, list):
            logger.warning("Invalid %s trade frame: expected a trade list", self.EXCHANGE)
            return
        loop = asyncio.get_running_loop()
        for message in messages:
            if not isinstance(message, dict):
                logger.warning("Invalid %s trade: expected an object", self.EXCHANGE)
                continue
            try:
                self._pending.put_nowait((loop.time(), message))
            except asyncio.QueueFull:
                raise BufferError(
                    f"{self.EXCHANGE} trade buffer is full; reconnecting (unbuffered trades may be lost)"
                ) from None
            self._received += 1
            self._peak_queue = max(self._peak_queue, self._pending.qsize())

    def extra_metrics(self):
        return ""

    async def _publish_batches(self):
        loop = asyncio.get_running_loop()
        store = TradeStatsStore()
        processed = reported = last_received = 0
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
                            async with asyncio.timeout(remaining):
                                items.append(await self._pending.get())
                        except TimeoutError:
                            break

                batch = await loop.run_in_executor(
                    self._publisher_executor, TradeBatch, [message for _, message in items], self.SERIALIZER
                )
                retry_delay = 1.0
                while True:
                    try:
                        await loop.run_in_executor(self._publisher_executor, batch.process, store)
                        break
                    except Exception:
                        logger.exception("%s batch failed; retrying in %s seconds", self.EXCHANGE, retry_delay)
                        await asyncio.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 10.0)

                processed += len(items)
                elapsed = loop.time() - last_report
                if elapsed >= self.REPORT_INTERVAL:
                    logger.info(
                        "%s throughput: received=%s processed=%s queued=%s oldest_batch_age=%.3fs "
                        "received_per_s=%.1f processed_per_s=%.1f peak_queue=%s loop_lag_max=%.3fs%s",
                        self.EXCHANGE,
                        self._received,
                        processed,
                        self._pending.qsize(),
                        loop.time() - items[0][0],
                        (self._received - last_received) / elapsed,
                        (processed - reported) / elapsed,
                        self._peak_queue,
                        self._loop_lag,
                        self.extra_metrics(),
                    )
                    last_report, reported, last_received = loop.time(), processed, self._received
                    self._peak_queue, self._loop_lag = self._pending.qsize(), 0.0
            finally:
                for _ in items:
                    self._pending.task_done()

    async def receive(self, ws, timeout=None):
        async with asyncio.timeout(self.RECEIVE_TIMEOUT if timeout is None else timeout):
            return await ws.recv()

    async def send(self, ws, message):
        async with asyncio.timeout(self.SEND_TIMEOUT):
            await ws.send(message)

    async def process(self, symbol_or_symbols):
        retry_delay = self.ITER_SLEEP
        while True:
            connected_at = None
            try:
                # Each exchange uses application heartbeats, checked by its reader.
                async with websockets.connect(self.URL, ping_interval=None, close_timeout=5, max_queue=32) as ws:
                    connected_at = monotonic()
                    for subscription in self.subscriptions(symbol_or_symbols):
                        await self.send(ws, json.dumps(subscription))
                    logger.info("%s stream connected: %s", self.EXCHANGE, symbol_or_symbols)
                    await self._read_stream(ws)
            except Exception as error:
                if connected_at is not None and monotonic() - connected_at >= self.MAX_RETRY_DELAY:
                    retry_delay = self.ITER_SLEEP
                logger.warning(
                    "%s stream %s failed: %s: %s. Reconnecting in %s seconds...",
                    self.EXCHANGE,
                    symbol_or_symbols,
                    type(error).__name__,
                    error,
                    retry_delay,
                )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, self.MAX_RETRY_DELAY)
