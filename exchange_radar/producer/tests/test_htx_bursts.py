import asyncio
import gzip
import json
import threading
from unittest.mock import AsyncMock, Mock

import pytest
from websockets.asyncio.server import serve

from exchange_radar.producer.tasks import buffered, htx
from exchange_radar.producer.tests.test_htx import frame, packed, socket, trade


@pytest.fixture
def task():
    instance = htx.HtxTradesTask()
    yield instance
    instance._publisher_executor.shutdown(wait=True, cancel_futures=True)
    instance.loop.close()


@pytest.mark.asyncio
async def test_a_frame_larger_than_the_publisher_queue_is_accepted_atomically(task):
    count = task.MAX_PENDING_TRADES + 1
    ws = socket(frame(*[trade(id=i) for i in range(count)]), {"ping": 42})
    with pytest.raises(asyncio.CancelledError):
        await task._read_stream(ws)
    assert task._received == task._frame_trades == count
    assert task._frames.qsize() == 1
    assert task._pending.empty()
    ws.send.assert_awaited_once_with('{"pong": 42}')
    assert 0 < task._frame_bytes <= task.MAX_INGRESS_BYTES


@pytest.mark.asyncio
async def test_staging_waits_for_capacity_and_preserves_receive_time_and_order(task):
    task._pending = asyncio.Queue(maxsize=2)
    task._buffer_frame("market.btcusdt.trade.detail", [trade(id=i) for i in range(6)], 600)
    buffered_at = asyncio.get_running_loop().time()
    received_at = None
    worker = asyncio.create_task(task._stage_frames())
    try:
        await asyncio.sleep(0)
        assert task._pending.qsize() == 2
        assert task._frame_trades == 4
        assert task._frame_bytes == 600
        ws = socket({"ping": 55})
        with pytest.raises(asyncio.CancelledError):
            await task._read_stream(ws)
        ws.send.assert_awaited_once_with('{"pong": 55}')
        for expected_id in range(6):
            timestamp, message = await asyncio.wait_for(task._pending.get(), 1)
            if received_at is None:
                received_at = timestamp
                assert timestamp <= buffered_at
            assert timestamp == received_at
            assert message["id"] == expected_id
            assert message["channel"] == "market.btcusdt.trade.detail"
            task._pending.task_done()
        await asyncio.wait_for(task._frames.join(), 1)
        assert task._frame_bytes == task._frame_trades == 0
        assert task._received == 6
        assert task._peak_queue == 2
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", ["bytes", "frames"])
async def test_ingress_limits_reject_whole_frames_without_discarding_accepted_frames(task, limit):
    if limit == "bytes":
        task.MAX_INGRESS_BYTES = 100
    else:
        task._frames = asyncio.Queue(maxsize=1)
    first = [trade(id=1)]
    task._buffer_frame("market.btcusdt.trade.detail", first, 60)
    with pytest.raises(BufferError, match="HTX ingress buffer is full"):
        task._buffer_frame("market.btcusdt.trade.detail", [trade(id=2)], 60)
    assert task._received == task._frame_trades == 1
    assert task._frames.qsize() == 1
    assert task._frame_bytes == task._peak_frame_bytes == 60
    metrics = task.extra_metrics()
    assert "ingress_frames=1" in metrics
    assert "ingress_trades=1" in metrics
    assert "ingress_bytes=60" in metrics
    assert "peak_ingress_bytes=60" in metrics


@pytest.mark.asyncio
@pytest.mark.parametrize("compressed", [False, True])
async def test_single_oversized_frame_cannot_bypass_byte_limit(task, compressed):
    task.MAX_INGRESS_BYTES = 100
    payload = json.dumps(frame(trade(id=1)))
    ws = socket()
    ws.recv.side_effect = [gzip.compress(payload.encode()) if compressed else payload]
    with pytest.raises(BufferError, match="frame exceeds the ingress byte budget"):
        await task._read_stream(ws)
    assert task._frames.empty()
    assert task._frame_bytes == task._received == 0


@pytest.mark.asyncio
async def test_empty_and_invalid_frames_do_not_reserve_ingress_capacity(task, caplog):
    ws = socket(frame(), frame(1, None))
    with pytest.raises(asyncio.CancelledError):
        await task._read_stream(ws)
    assert task._frames.empty()
    assert task._received == task._frame_bytes == task._frame_trades == 0
    assert "Invalid HTX trade" in caplog.text


@pytest.mark.asyncio
async def test_reconnect_keeps_previously_accepted_frames(task, monkeypatch):
    first = socket(frame(*[trade(id=i) for i in range(6000)]))
    second = socket(
        {
            "rep": "market.btcusdt.trade.detail",
            "id": "htx-recovery-1",
            "status": "ok",
            "data": [trade(id=5999), trade(id=6000)],
        },
        frame(trade(id=6000)),
    )
    first.recv.side_effect = [packed(frame(*[trade(id=i) for i in range(6000)])), OSError("network lost")]
    monkeypatch.setattr(buffered.websockets, "connect", Mock(side_effect=[first, second]))
    monkeypatch.setattr(buffered.asyncio, "sleep", AsyncMock())
    with pytest.raises(asyncio.CancelledError):
        await task.process("BTCUSDT")
    assert task._received == task._frame_trades == 6001
    assert task._frames.qsize() == 2
    for ws in (first, second):
        ws.__aexit__.assert_awaited_once()
    # Reconnection must retain both frames, in arrival order.
    _, _, messages, _ = task._frames.get_nowait()
    assert [message["id"] for message in messages] == list(range(6000))
    assert task._frames.get_nowait()[2][0]["id"] == 6000


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "count,symbols,frame_size",
    [(12000, ("BTCUSDT",), 12000), (10000, ("BTCUSDT", "ETHUSDT"), 500), (50000, ("BTCUSDT",), 1000)],
)
async def test_large_bursts_survive_blocked_publishing_and_keep_heartbeats(
    task, monkeypatch, count, symbols, frame_size
):
    started, release = threading.Event(), threading.Event()
    complete, finish = asyncio.Event(), asyncio.Event()
    delivered, pongs, errors, threads, connected = [], [], [], [], []
    monkeypatch.setattr(buffered, "TradeStatsStore", Mock())

    class Batch:
        def __init__(self, messages, serializer):
            assert serializer is task.SERIALIZER
            self.messages = messages
            threads.append(threading.get_ident())

        def process(self, store):
            threads.append(threading.get_ident())
            started.set()
            if not release.wait(10):
                raise TimeoutError("test publisher not released")
            delivered.extend(self.messages)

    monkeypatch.setattr(buffered, "TradeBatch", Batch)

    async def server(ws):
        try:
            subscription = json.loads(await ws.recv())["sub"]
            for offset in range(0, count, frame_size):
                await ws.send(
                    packed(
                        frame(
                            *[trade(id=i) for i in range(offset, min(offset + frame_size, count))],
                            channel=subscription,
                        )
                    )
                )
            assert await asyncio.wait_for(asyncio.to_thread(started.wait, 3), 4)
            for ping in range(4):
                await ws.send(packed({"ping": ping}))
                assert json.loads(await asyncio.wait_for(ws.recv(), 1)) == {"pong": ping}
                pongs.append((subscription, ping))
            connected.append(subscription)
            if len(connected) == len(symbols):
                complete.set()
            await finish.wait()
        except Exception as error:
            errors.append(error)
            complete.set()

    async with serve(server, "127.0.0.1", 0) as ws_server:
        task.URL = f"ws://127.0.0.1:{ws_server.sockets[0].getsockname()[1]}"
        worker = asyncio.create_task(task.task(symbols))
        try:
            await asyncio.wait_for(complete.wait(), 8)
            assert not errors, errors
            assert len(pongs) == 4 * len(symbols)
            assert task._received == count * len(symbols)
            assert delivered == []
            assert task._frame_trades > 0
            assert 0 < task._frame_bytes <= task.MAX_INGRESS_BYTES
            assert task._pending.qsize() <= task.MAX_PENDING_TRADES
            release.set()
            await asyncio.wait_for(task._frames.join(), 8)
            await asyncio.wait_for(task._pending.join(), 8)
            assert task._frame_bytes == task._frame_trades == 0
            assert len(delivered) == count * len(symbols)
            for symbol in symbols:
                channel = f"market.{symbol.lower()}.trade.detail"
                assert [message["id"] for message in delivered if message["channel"] == channel] == list(range(count))
            assert len(set(threads)) == 1
            assert threads[0] != threading.get_ident()
        finally:
            release.set()
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
            finish.set()
