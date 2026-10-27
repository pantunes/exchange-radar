import asyncio
import gzip
import json
import logging
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from io import BytesIO

from exchange_radar.producer.serializers.htx import HtxTradeSerializer
from exchange_radar.producer.tasks.buffered import BufferedTradesTask

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@dataclass
class Recovery:
    cursor: tuple[str, int]
    request_id: str = ""
    deadline: float = 0
    frames: list = field(default_factory=list)
    size: int = 0


class HtxTradesTask(BufferedTradesTask):
    EXCHANGE = "HTX"
    SERIALIZER = HtxTradeSerializer
    URL = "wss://api.huobi.pro/ws"
    # Budget decompressed JSON bytes; parsed Python objects add memory overhead.
    MAX_INGRESS_BYTES = 8 * 1024 * 1024
    MAX_INGRESS_FRAMES = 4096
    MAX_SEEN_TRADES = 4096
    HISTORY_LIMIT = 300
    RECOVERY_TIMEOUT = 10.0

    def __init__(self):
        super().__init__()
        self._frames = asyncio.Queue(maxsize=self.MAX_INGRESS_FRAMES)
        self._frame_bytes = 0
        self._frame_trades = 0
        self._peak_frame_bytes = 0
        self._active_frame = False
        self._last_trade = {}
        self._untracked_channels = set()
        self._seen = defaultdict(OrderedDict)
        self._recoveries = {}
        self._held_bytes = self._held_frames = self._request_sequence = 0

    async def task(self, symbols):
        async with asyncio.TaskGroup() as group:
            group.create_task(self._stage_frames())
            group.create_task(super().task(symbols))

    def _buffer_frame(self, channel, messages, size):
        messages = [message for message in messages if self._valid_message(message)]
        if not messages:
            return
        if (
            self._frames.full()
            or self._frames.qsize() + self._held_frames >= self.MAX_INGRESS_FRAMES
            or self._frame_bytes + self._held_bytes + size > self.MAX_INGRESS_BYTES
        ):
            raise BufferError("HTX ingress buffer is full; reconnecting (unbuffered trades may be lost)")
        self._frames.put_nowait((asyncio.get_running_loop().time(), channel, messages, size))
        self._frame_bytes += size
        self._frame_trades += len(messages)
        self._received += len(messages)
        self._peak_frame_bytes = max(self._peak_frame_bytes, self._frame_bytes)

    @staticmethod
    def _trade_key(message):
        """Use opaque IDs for equality; HTX doesn't promise contiguous trade IDs."""
        if not isinstance(message, dict):
            return None
        identity = message.get("tradeId", message.get("id"))
        timestamp = message.get("ts")
        if isinstance(identity, bool) or isinstance(timestamp, bool):
            return None
        if not isinstance(identity, (str, int)) or not str(identity).isdigit():
            return None
        if not isinstance(timestamp, int) or timestamp < 0:
            return None
        return str(identity), timestamp

    def _admit_frame(self, channel, messages, size):
        seen, identities, accepted = self._seen[channel], set(), []
        for message in messages:
            key = self._trade_key(message)
            if key is not None:
                if key[0] in seen or key[0] in identities:
                    continue
                identities.add(key[0])
            accepted.append(message)
        # Only advance the cursor once the bounded ingress queue owns the frame.
        self._buffer_frame(channel, accepted, size)
        for message in accepted:
            key = self._trade_key(message)
            if key is not None:
                seen[key[0]] = None
                self._last_trade[channel] = key
                if len(seen) > self.MAX_SEEN_TRADES:
                    seen.popitem(last=False)
            else:
                self._untracked_channels.add(channel)
        return len(accepted)

    def _hold_frame(self, channel, messages, size):
        if (
            self._frames.qsize() + self._held_frames >= self.MAX_INGRESS_FRAMES
            or self._frame_bytes + self._held_bytes + size > self.MAX_INGRESS_BYTES
        ):
            raise BufferError("HTX recovery buffer is full; unbuffered trades may be lost")
        recovery = self._recoveries[channel]
        recovery.frames.append(messages)
        recovery.size += size
        self._held_bytes += size
        self._held_frames += 1

    def _finish_recovery(self, channel, history=None, reason=None):
        recovery = self._recoveries[channel]
        if history is not None and (
            not isinstance(history, list)
            or len(history) > self.HISTORY_LIMIT
            or any(self._trade_key(message) is None for message in history)
        ):
            history, reason = None, "invalid history response"
        if history is not None:
            try:
                for message in history:
                    self.SERIALIZER(_defer_stats=True, channel=channel, **message)
            except (ValueError, TypeError, KeyError):
                history, reason = None, "invalid history trade"
        covered = history is not None and any(self._trade_key(message)[0] == recovery.cursor[0] for message in history)
        messages = [message for message in history or [] if message["ts"] >= recovery.cursor[1]]
        messages.extend(message for frame in recovery.frames for message in frame)

        # Malformed live trades still reach the existing isolated validation path;
        # they must not poison recovery's sorting and cause endless reconnects.
        def sort_key(message):
            identity, timestamp = self._trade_key(message) or ("", -1)
            return timestamp, len(identity), identity

        messages.sort(key=sort_key)
        size = len(json.dumps(messages, default=str).encode("utf-8"))
        # Transfer the held budget to normal ingress atomically, retaining it on failure.
        self._held_bytes -= recovery.size
        self._held_frames -= len(recovery.frames)
        try:
            forwarded = self._admit_frame(channel, messages, size)
        except Exception:
            self._held_bytes += recovery.size
            self._held_frames += len(recovery.frames)
            raise
        del self._recoveries[channel]
        if covered:
            logger.info("HTX recovery complete: %s history=%s forwarded=%s", channel, len(history), forwarded)
        else:
            logger.warning(
                "HTX recovery incomplete: %s; %s; gap may remain (history=%s forwarded=%s)",
                channel,
                reason or "history does not include the previous trade",
                len(history or []),
                forwarded,
            )

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
            f" recovery_frames={self._held_frames} recovery_bytes={self._held_bytes}"
        )
        self._peak_frame_bytes = self._frame_bytes
        return metrics

    def streams(self, symbols):
        return symbols

    def subscriptions(self, symbol):
        return [{"sub": f"market.{symbol.lower()}.trade.detail"}]

    async def _read_connected_stream(self, ws, stream):
        channel = f"market.{stream.lower()}.trade.detail"
        if channel in self._untracked_channels:
            logger.warning(
                "HTX recovery incomplete: %s; previous trades lacked usable IDs/timestamps; gap may remain", channel
            )
        if channel in self._last_trade:
            # Keep already held live trades if another disconnect interrupts recovery.
            recovery = self._recoveries.setdefault(channel, Recovery(self._last_trade[channel]))
            self._request_sequence += 1
            recovery.request_id = f"htx-recovery-{self._request_sequence}"
            recovery.deadline = asyncio.get_running_loop().time() + self.RECOVERY_TIMEOUT
            await self.send(ws, json.dumps({"req": channel, "id": recovery.request_id}))
        await self._read_stream(ws, channel)

    async def _read_stream(self, ws, stream_channel=None):
        while True:
            recovery = self._recoveries.get(stream_channel)
            timeout = self.RECEIVE_TIMEOUT
            if recovery is not None:
                remaining = recovery.deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    self._finish_recovery(stream_channel, reason="history request timed out")
                    continue
                timeout = min(timeout, remaining)
            try:
                payload = await self.receive(ws, timeout=timeout)
            except TimeoutError:
                if recovery is None:
                    raise
                self._finish_recovery(stream_channel, reason="history request timed out")
                continue
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
            if recovery is not None and response.get("id") == recovery.request_id:
                if response.get("status") == "ok" and response.get("rep") == stream_channel:
                    self._finish_recovery(stream_channel, history=response.get("data"))
                else:
                    self._finish_recovery(stream_channel, reason="history request rejected or mismatched")
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
                if stream_channel is not None and channel != stream_channel:
                    raise ValueError("unexpected trade channel")
            except (KeyError, TypeError, ValueError) as error:
                logger.warning("Invalid HTX trade frame: %s", error)
                continue
            messages = [message for message in messages if self._valid_message(message)]
            if channel in self._recoveries:
                self._hold_frame(channel, messages, size)
            else:
                self._admit_frame(channel, messages, size)
            del response, messages, decoded, payload
            await asyncio.sleep(0)
