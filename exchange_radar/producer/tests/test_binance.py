import asyncio
import json
import threading
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from exchange_radar.producer.tasks import binance


@pytest.fixture
def task():
    instance = binance.BinanceTradesTask()
    yield instance
    instance._publisher_executor.shutdown(wait=True, cancel_futures=True)
    instance.loop.close()


def payload(trade_id=1, symbol="BTCUSDT"):
    return json.dumps({"e": "trade", "s": symbol, "t": trade_id}).encode()


def make_socket(*messages):
    socket = MagicMock()
    socket.__aenter__.return_value = socket
    socket.__aexit__.return_value = False
    socket.recv = AsyncMock(side_effect=messages)
    return socket


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["read", "error", "serverShutdown", "code", "connect", "close"])
async def test_failed_stream_reconnects_and_keeps_accepted_trades(task, monkeypatch, failure):
    first = make_socket(payload(1), OSError("closed"))
    if failure in ("error", "serverShutdown"):
        first.recv.side_effect = [payload(1), json.dumps({"e": failure}).encode()]
    elif failure == "code":
        first.recv.side_effect = [payload(1), b'{"code":-1,"msg":"unavailable"}']
    elif failure == "connect":
        first.__aenter__.side_effect = OSError("connection lost")
    elif failure == "close":
        first.__aexit__.side_effect = OSError("connection already lost")
    second = make_socket(payload(2), asyncio.CancelledError())
    connect = Mock(side_effect=[first, second])
    monkeypatch.setattr(binance.websockets, "connect", connect)
    sleep = AsyncMock()
    monkeypatch.setattr(binance.asyncio, "sleep", sleep)

    with pytest.raises(asyncio.CancelledError):
        await task.process("BTCUSDT")

    assert connect.call_count == 2
    sleep.assert_awaited_once_with(task.ITER_SLEEP)
    accepted = []
    while not task._pending.empty():
        accepted.append(json.loads(task._pending.get_nowait()[1])["t"])
    assert accepted == ([2] if failure == "connect" else [1, 2])
    assert task._received == len(accepted)
    assert connect.call_args.args == ("wss://stream.binance.com:9443/ws/btcusdt@trade",)
    assert connect.call_args.kwargs["max_queue"] == 32
    assert connect.call_args.kwargs["max_size"] == task.MAX_MESSAGE_BYTES
    if failure != "connect":
        first.__aexit__.assert_called_once()
    else:
        first.__aexit__.assert_not_called()
    second.__aexit__.assert_called_once()


@pytest.mark.asyncio
async def test_repeated_startup_failures_back_off_with_a_limit(task, monkeypatch):
    connect = Mock(side_effect=[OSError("offline")] * 5 + [asyncio.CancelledError()])
    monkeypatch.setattr(binance.websockets, "connect", connect)
    sleep = AsyncMock()
    monkeypatch.setattr(binance.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        await task.process("BTCUSDT")
    assert [call.args[0] for call in sleep.await_args_list] == [10.0, 20.0, 40.0, 60.0, 60.0]


@pytest.mark.asyncio
async def test_cancellation_during_backoff_stops_reconnecting(task, monkeypatch):
    connect = Mock(return_value=make_socket(OSError("closed")))
    monkeypatch.setattr(binance.websockets, "connect", connect)
    monkeypatch.setattr(binance.asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError()))
    with pytest.raises(asyncio.CancelledError):
        await task.process("BTCUSDT")
    connect.assert_called_once()


@pytest.mark.asyncio
async def test_backoff_resets_after_a_stable_connection(task, monkeypatch):
    connect = Mock(side_effect=[make_socket(OSError("lost")), make_socket(OSError("lost")), asyncio.CancelledError()])
    monkeypatch.setattr(binance.websockets, "connect", connect)
    monkeypatch.setattr(binance, "monotonic", Mock(side_effect=[0, 1, 2, 100]))
    sleep = AsyncMock()
    monkeypatch.setattr(binance.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        await task.process("BTCUSDT")
    assert [call.args[0] for call in sleep.await_args_list] == [10.0, 10.0]


@pytest.mark.asyncio
async def test_malformed_and_non_trade_frames_do_not_poison_the_inbox(task, caplog):
    socket = make_socket(b"broken", b"\xff", b"[]", b'{"e":"unknown"}', payload(), asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await task._read_stream(socket)
    assert task._received == 1
    assert task._pending.get_nowait()[1] == payload()
    assert "Invalid Binance JSON frame" in caplog.text
    assert "expected an object" in caplog.text
    assert "Unexpected Binance event" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("count, sizes", [(53, [50, 3]), (1, [1]), (453, [200, 200, 50, 3])])
async def test_batches_preserve_order_and_flush_small_batches(task, monkeypatch, caplog, count, sizes):
    batches = []
    task.REPORT_INTERVAL = 0
    monkeypatch.setattr(binance, "TradeStatsStore", Mock())

    class Batch:
        def __init__(self, messages):
            self.messages = messages

        def process(self, store):
            batches.append(self.messages)

    monkeypatch.setattr(binance, "TradeBatch", Batch)
    for i in range(count):
        task.enqueue_payload(payload(i))
    worker = asyncio.create_task(task._publish_batches())
    try:
        await asyncio.wait_for(task._pending.join(), 2)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
    assert [len(batch) for batch in batches] == sizes
    assert [trade["t"] for batch in batches for trade in batch] == list(range(count))
    assert task._pending_bytes == task._pending_count == 0
    assert "pending_bytes=" in caplog.text
    assert "processed_per_s=" in caplog.text


@pytest.mark.asyncio
async def test_failed_batch_is_retried_before_later_trades_without_rebuilding(task, monkeypatch):
    task.BATCH_SIZE = 1
    attempts, created = [], []
    monkeypatch.setattr(binance, "TradeStatsStore", Mock())
    monkeypatch.setattr(binance.asyncio, "sleep", AsyncMock())

    class Batch:
        def __init__(self, messages):
            self.message = messages[0]
            created.append(self.message["t"])

        def process(self, store):
            attempts.append(self.message["t"])
            if len(attempts) < 3:
                raise ConnectionError("temporary database failure")

    monkeypatch.setattr(binance, "TradeBatch", Batch)
    for i in (1, 2):
        task.enqueue_payload(payload(i))
    worker = asyncio.create_task(task._publish_batches())
    try:
        await asyncio.wait_for(task._pending.join(), 2)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
    assert attempts == [1, 1, 1, 2]
    assert created == [1, 2]
    assert [call.args[0] for call in binance.asyncio.sleep.await_args_list] == [1.0, 2.0]
    assert task._pending_bytes == task._pending_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("bound", ["count", "bytes"])
async def test_inbox_bounds_include_inflight_trades_until_publishing_finishes(task, monkeypatch, bound):
    started, release = threading.Event(), threading.Event()
    threads = []
    if bound == "count":
        task.MAX_PENDING_TRADES = 1
    else:
        task.MAX_PENDING_BYTES = len(payload())
    monkeypatch.setattr(binance, "TradeStatsStore", Mock())

    class Batch:
        def __init__(self, messages):
            threads.append(threading.get_ident())

        def process(self, store):
            threads.append(threading.get_ident())
            started.set()
            if not release.wait(5):
                raise TimeoutError("test publisher not released")

    monkeypatch.setattr(binance, "TradeBatch", Batch)
    task.enqueue_payload(payload())
    worker = asyncio.create_task(task._publish_batches())
    try:
        assert await asyncio.wait_for(asyncio.to_thread(started.wait, 2), 3)
        assert task._pending.empty()
        assert task._pending_bytes == len(payload())
        with pytest.raises(BufferError, match="unbuffered trades may be lost"):
            task.enqueue_payload(payload(2))
        assert task._received == 1
        release.set()
        await asyncio.wait_for(task._pending.join(), 2)
        task.enqueue_payload(payload(2))
        await asyncio.wait_for(task._pending.join(), 2)
    finally:
        release.set()
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
    assert task._pending_bytes == task._pending_count == 0
    assert len(set(threads)) == 1
    assert threads[0] != threading.get_ident()


@pytest.mark.asyncio
async def test_buffer_exhaustion_is_explicit_and_keeps_previously_accepted_trades(task, monkeypatch, caplog):
    task.MAX_PENDING_TRADES = 2
    socket = make_socket(payload(1), payload(2), payload(3))
    monkeypatch.setattr(binance.websockets, "connect", Mock(return_value=socket))
    monkeypatch.setattr(binance.asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError()))
    with pytest.raises(asyncio.CancelledError):
        await task.process("BTCUSDT")
    assert task._received == 2
    assert [json.loads(task._pending.get_nowait()[1])["t"] for _ in range(2)] == [1, 2]
    assert "burst inbox exhausted" in caplog.text
    assert "pending=2" in caplog.text
