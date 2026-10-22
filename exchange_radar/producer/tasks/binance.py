import asyncio
import json
import logging
from time import monotonic

import websockets

from exchange_radar.producer.batching import TradeBatch, TradeStatsStore
from exchange_radar.producer.tasks.buffered import BufferedTradesTask

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class WireBatch:
    """Build models and publish on the same worker, retaining retry progress."""

    def __init__(self, payloads):
        self.payloads = payloads
        self.batch = None

    def process(self, store):
        if self.batch is None:
            self.batch = TradeBatch([json.loads(payload) for payload in self.payloads])
            self.payloads = None
        self.batch.process(store)


class BinanceTradesTask(BufferedTradesTask):
    EXCHANGE = "Binance"
    URL = "wss://stream.binance.com:9443/ws/{symbol}@trade"
    MAX_PENDING_TRADES = 50_000
    MAX_PENDING_BYTES = 16 * 1024 * 1024
    MAX_MESSAGE_BYTES = 64 * 1024
    BURST_BATCH_SIZE = 200

    def __init__(self):
        super().__init__()
        self._pending_bytes = 0
        self._pending_count = 0
        self._peak_bytes = 0

    def streams(self, symbols):
        return symbols

    def enqueue_payload(self, payload):
        # Retain wire bytes, not thousands of parsed dictionaries/models. Credits
        # include the in-flight batch and are released only after publishing.
        if (
            self._pending_count >= self.MAX_PENDING_TRADES
            or self._pending_bytes + len(payload) > self.MAX_PENDING_BYTES
        ):
            raise BufferError(
                "Binance burst inbox exhausted "
                f"(pending={self._pending_count}, bytes={self._pending_bytes}); "
                "reconnecting (unbuffered trades may be lost)"
            )
        self._pending.put_nowait((asyncio.get_running_loop().time(), payload))
        self._pending_count += 1
        self._pending_bytes += len(payload)
        self._received += 1
        self._peak_queue = max(self._peak_queue, self._pending_count)
        self._peak_bytes = max(self._peak_bytes, self._pending_bytes)

    async def _publish_batches(self):
        loop = asyncio.get_running_loop()
        store = TradeStatsStore()
        processed = reported = last_received = 0
        last_report = loop.time()
        while True:
            items = [await self._pending.get()]
            try:
                # Avoid adding latency to quiet streams; amortize Redis and
                # executor round trips more aggressively when already behind.
                limit = (
                    self.BURST_BATCH_SIZE if self._pending.qsize() + 1 >= self.BURST_BATCH_SIZE else self.BATCH_SIZE
                )
                deadline = loop.time() + self.BATCH_WAIT
                while len(items) < limit:
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

                batch = WireBatch([payload for _, payload in items])
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
                elapsed = loop.time() - last_report
                if elapsed >= self.REPORT_INTERVAL:
                    logger.info(
                        "Binance throughput: received=%s processed=%s queued=%s oldest_batch_age=%.3fs "
                        "received_per_s=%.1f processed_per_s=%.1f peak_queue=%s loop_lag_max=%.3fs "
                        "pending_bytes=%s peak_pending_bytes=%s",
                        self._received,
                        processed,
                        self._pending.qsize(),
                        loop.time() - items[0][0],
                        (self._received - last_received) / elapsed,
                        (processed - reported) / elapsed,
                        self._peak_queue,
                        self._loop_lag,
                        self._pending_bytes - sum(len(payload) for _, payload in items),
                        self._peak_bytes,
                    )
                    last_report, reported, last_received = loop.time(), processed, self._received
                    self._peak_queue = self._pending_count - len(items)
                    self._peak_bytes = self._pending_bytes - sum(len(payload) for _, payload in items)
                    self._loop_lag = 0.0
            finally:
                for _, payload in items:
                    self._pending_count -= 1
                    self._pending_bytes -= len(payload)
                    self._pending.task_done()

    async def _read_stream(self, ws):
        while True:
            payload = await ws.recv(decode=False)
            try:
                message = json.loads(payload)
            except (ValueError, UnicodeDecodeError):
                logger.warning("Invalid Binance JSON frame")
                continue
            if not isinstance(message, dict):
                logger.warning("Invalid Binance frame: expected an object")
            elif message.get("e") in ("error", "serverShutdown") or "code" in message:
                raise ConnectionError(f"Binance control message: {message}")
            elif message.get("e") == "trade":
                self.enqueue_payload(payload)
            else:
                logger.warning("Unexpected Binance event: %s", message.get("e"))

    async def process(self, symbol_or_symbols):
        retry_delay = self.ITER_SLEEP
        while True:
            connected_at = None
            try:
                # The transport's bounded frame queue applies flow control,
                # unlike the SDK's extra queue which fails at 5000 messages.
                async with websockets.connect(
                    self.URL.format(symbol=symbol_or_symbols.lower()),
                    ping_interval=20,
                    ping_timeout=60,
                    close_timeout=5,
                    max_size=self.MAX_MESSAGE_BYTES,
                    max_queue=32,
                ) as ws:
                    connected_at = monotonic()
                    logger.info("Binance stream connected: %s", symbol_or_symbols)
                    await self._read_stream(ws)
            except Exception as error:
                if connected_at is not None and monotonic() - connected_at >= self.MAX_RETRY_DELAY:
                    retry_delay = self.ITER_SLEEP
                logger.warning(
                    "Binance stream %s failed: %s: %s. Reconnecting in %s seconds...",
                    symbol_or_symbols,
                    type(error).__name__,
                    error,
                    retry_delay,
                )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, self.MAX_RETRY_DELAY)
