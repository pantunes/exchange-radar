import asyncio
import gzip
import json
import logging
from decimal import Decimal
from io import BytesIO

from exchange_radar.producer.serializers.htx import HtxTradeSerializer
from exchange_radar.producer.tasks.buffered import BufferedTradesTask

logger = logging.getLogger(__name__)


class HtxTradesTask(BufferedTradesTask):
    EXCHANGE = "HTX"
    SERIALIZER = HtxTradeSerializer
    URL = "wss://api.huobi.pro/ws"
    # Budget decompressed JSON bytes; parsed Python objects add memory overhead.
    MAX_INGRESS_BYTES = 8 * 1024 * 1024
    MAX_INGRESS_FRAMES = 4096

    def __init__(self):
        super().__init__()
        self._frames = asyncio.Queue(maxsize=self.MAX_INGRESS_FRAMES)
        self._frame_bytes = 0
        self._frame_trades = 0
        self._peak_frame_bytes = 0
        self._active_frame = False

    async def task(self, symbols):
        async with asyncio.TaskGroup() as group:
            group.create_task(self._stage_frames())
            group.create_task(super().task(symbols))

    def _buffer_frame(self, channel, messages, size):
        messages = [message for message in messages if self._valid_message(message)]
        if not messages:
            return
        if self._frames.full() or self._frame_bytes + size > self.MAX_INGRESS_BYTES:
            raise BufferError("HTX ingress buffer is full; reconnecting (unbuffered trades may be lost)")
        self._frames.put_nowait((asyncio.get_running_loop().time(), channel, messages, size))
        self._frame_bytes += size
        self._frame_trades += len(messages)
        self._received += len(messages)
        self._peak_frame_bytes = max(self._peak_frame_bytes, self._frame_bytes)

    @staticmethod
    def _valid_message(message):
        if isinstance(message, dict):
            return True
        logger.warning("Invalid HTX trade: expected an object")
        return False

    async def _stage_frames(self):
        while True:
            received_at, channel, messages, size = await self._frames.get()
            self._active_frame = True
            try:
                for index, message in enumerate(messages):
                    message["channel"] = channel
                    await self._pending.put((received_at, message))
                    self._frame_trades -= 1
                    self._peak_queue = max(self._peak_queue, self._pending.qsize())
                    # Release the frame's reference once the publisher queue owns it.
                    messages[index] = None
            finally:
                self._frame_bytes -= size
                self._frames.task_done()
                self._active_frame = False
                del messages

    def extra_metrics(self):
        metrics = (
            f" ingress_frames={self._frames.qsize() + int(self._active_frame)}"
            f" ingress_trades={self._frame_trades} ingress_bytes={self._frame_bytes}"
            f" peak_ingress_bytes={self._peak_frame_bytes}"
        )
        self._peak_frame_bytes = self._frame_bytes
        return metrics

    def streams(self, symbols):
        return symbols

    def subscriptions(self, symbol):
        return [{"sub": f"market.{symbol.lower()}.trade.detail"}]

    async def _read_stream(self, ws):
        while True:
            payload = await self.receive(ws)
            try:
                if isinstance(payload, bytes):
                    with gzip.GzipFile(fileobj=BytesIO(payload)) as compressed:
                        decoded = compressed.read(self.MAX_INGRESS_BYTES + 1)
                else:
                    decoded = payload
                size = len(decoded) if isinstance(decoded, bytes) else len(decoded.encode("utf-8"))
                if size > self.MAX_INGRESS_BYTES:
                    raise BufferError("HTX frame exceeds the ingress byte budget; unbuffered trades may be lost")
                response = json.loads(decoded, parse_float=Decimal)
                if not isinstance(response, dict):
                    raise ValueError("expected a JSON object")
            except (OSError, EOFError, UnicodeDecodeError, ValueError) as error:
                logger.warning("Invalid HTX frame: %s", error)
                continue

            if "ping" in response:
                await self.send(ws, json.dumps({"pong": response["ping"]}))
                continue
            if response.get("status") == "error":
                raise RuntimeError(f"HTX subscription failed: {response}")
            if "tick" not in response:
                continue
            try:
                channel = response["ch"]
                messages = response["tick"]["data"]
                if not isinstance(channel, str) or not isinstance(messages, list):
                    raise ValueError("expected a channel and trade list")
            except (KeyError, TypeError, ValueError) as error:
                logger.warning("Invalid HTX trade frame: %s", error)
                continue
            self._buffer_frame(channel, messages, size)
            del response, messages, decoded, payload
            await asyncio.sleep(0)
