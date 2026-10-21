import asyncio
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


def make_client():
    client = Mock()
    client.close_connection = AsyncMock()
    return client


def make_socket(*messages):
    socket = MagicMock()
    socket.__aenter__.return_value = socket
    socket.__aexit__.return_value = False
    socket.recv = AsyncMock(side_effect=messages)
    return socket


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["read", "overflow", "error_message", "connect", "close"])
async def test_failed_stream_reconnects_and_keeps_receiving(task, monkeypatch, failure):
    clients = [make_client(), make_client()]
    first = make_socket(binance.exceptions.ReadLoopClosed("closed"))
    if failure == "overflow":
        first.recv.side_effect = binance.exceptions.BinanceWebsocketQueueOverflow("queue full")
    elif failure == "error_message":
        first.recv.side_effect = [{"e": "error", "m": "queue full"}]
    elif failure == "connect":
        first.__aenter__.side_effect = OSError("connection lost")
    elif failure == "close":
        clients[0].close_connection.side_effect = OSError("connection already lost")
    second = make_socket({"s": "BTCUSDT"}, asyncio.CancelledError())
    managers = [Mock(), Mock()]
    managers[0].trade_socket.return_value = first
    managers[1].trade_socket.return_value = second
    create = AsyncMock(side_effect=clients)
    monkeypatch.setattr(binance.AsyncClient, "create", create)
    monkeypatch.setattr(binance, "BinanceSocketManager", Mock(side_effect=managers))
    sleep = AsyncMock()
    monkeypatch.setattr(binance.asyncio, "sleep", sleep)

    with pytest.raises(asyncio.CancelledError):
        await task.process("BTCUSDT")

    assert create.await_count == 2
    sleep.assert_awaited_once_with(task.ITER_SLEEP)
    assert task._pending.get_nowait()[1] == {"s": "BTCUSDT"}
    assert task._received == 1
    for client, manager in zip(clients, managers):
        client.close_connection.assert_awaited_once()
        manager.trade_socket.assert_called_once_with("BTCUSDT")


@pytest.mark.asyncio
async def test_repeated_startup_failures_back_off_with_a_limit(task, monkeypatch):
    create = AsyncMock(side_effect=[OSError("offline")] * 5 + [asyncio.CancelledError()])
    monkeypatch.setattr(binance.AsyncClient, "create", create)
    sleep = AsyncMock()
    monkeypatch.setattr(binance.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        await task.process("BTCUSDT")
    assert [call.args[0] for call in sleep.await_args_list] == [10.0, 20.0, 40.0, 60.0, 60.0]


@pytest.mark.asyncio
async def test_cancellation_during_backoff_stops_reconnecting(task, monkeypatch):
    client = make_client()
    create = AsyncMock(return_value=client)
    monkeypatch.setattr(binance.AsyncClient, "create", create)
    manager = Mock()
    manager.trade_socket.return_value = make_socket(binance.exceptions.ReadLoopClosed("closed"))
    monkeypatch.setattr(binance, "BinanceSocketManager", Mock(return_value=manager))
    monkeypatch.setattr(binance.asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError()))
    with pytest.raises(asyncio.CancelledError):
        await task.process("BTCUSDT")
    create.assert_awaited_once()
    client.close_connection.assert_awaited_once()


@pytest.mark.asyncio
async def test_backoff_resets_after_a_stable_connection(task, monkeypatch):
    clients = [make_client(), make_client()]
    monkeypatch.setattr(binance.AsyncClient, "create", AsyncMock(side_effect=[*clients, asyncio.CancelledError()]))
    manager = Mock()
    manager.trade_socket.side_effect = [make_socket(OSError("lost")), make_socket(OSError("lost again"))]
    monkeypatch.setattr(binance, "BinanceSocketManager", Mock(return_value=manager))
    monkeypatch.setattr(binance, "monotonic", Mock(side_effect=[0, 1, 2, 100]))
    sleep = AsyncMock()
    monkeypatch.setattr(binance.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        await task.process("BTCUSDT")
    assert [call.args[0] for call in sleep.await_args_list] == [10.0, 10.0]
    for client in clients:
        client.close_connection.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("count, sizes", [(53, [50, 3]), (1, [1])])
async def test_batches_preserve_order_and_flush_small_batches(task, monkeypatch, count, sizes):
    batches = []
    monkeypatch.setattr(binance, "TradeStatsStore", Mock())

    class Batch:
        def __init__(self, messages):
            self.messages = messages

        def process(self, store):
            batches.append(self.messages)

    monkeypatch.setattr(binance, "TradeBatch", Batch)
    for i in range(count):
        task._pending.put_nowait((0, {"t": i}))
    worker = asyncio.create_task(task._publish_batches())
    try:
        await asyncio.wait_for(task._pending.join(), 2)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
    assert [len(batch) for batch in batches] == sizes
    assert [trade["t"] for batch in batches for trade in batch] == list(range(count))


@pytest.mark.asyncio
async def test_failed_batch_is_retried_before_later_trades(task, monkeypatch):
    task.BATCH_SIZE = 1
    attempts = []
    monkeypatch.setattr(binance, "TradeStatsStore", Mock())
    monkeypatch.setattr(binance.asyncio, "sleep", AsyncMock())

    class Batch:
        def __init__(self, messages):
            self.message = messages[0]

        def process(self, store):
            attempts.append(self.message["t"])
            if len(attempts) < 3:
                raise ConnectionError("temporary database failure")

    monkeypatch.setattr(binance, "TradeBatch", Batch)
    for i in (1, 2):
        task._pending.put_nowait((0, {"t": i}))
    worker = asyncio.create_task(task._publish_batches())
    try:
        await asyncio.wait_for(task._pending.join(), 2)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
    assert attempts == [1, 1, 1, 2]
    assert [call.args[0] for call in binance.asyncio.sleep.await_args_list] == [1.0, 2.0]


@pytest.mark.asyncio
async def test_socket_reads_continue_while_a_batch_is_blocked(task, monkeypatch):
    started, release = threading.Event(), threading.Event()
    worker_threads, published = [], []
    monkeypatch.setattr(binance, "TradeStatsStore", Mock())

    class Batch:
        def __init__(self, messages):
            worker_threads.append(threading.get_ident())
            self.messages = messages

        def process(self, store):
            worker_threads.append(threading.get_ident())
            if not published:
                started.set()
                if not release.wait(5):
                    raise TimeoutError("test publisher not released")
            published.extend(self.messages)

    monkeypatch.setattr(binance, "TradeBatch", Batch)
    sockets = []
    for symbol in ("BTCUSDT", "ETHUSDT"):
        messages = [{"s": symbol, "t": i} for i in range(100)]

        def receiver(messages=messages):
            iterator = iter(messages)

            async def recv():
                message = next(iterator, None)
                if message is not None:
                    return message
                await asyncio.Event().wait()

            return recv

        socket = make_socket()
        socket.recv.side_effect = receiver()
        sockets.append(socket)
    clients = [make_client(), make_client()]
    monkeypatch.setattr(binance.AsyncClient, "create", AsyncMock(side_effect=clients))
    managers = [Mock(), Mock()]
    for manager, socket in zip(managers, sockets):
        manager.trade_socket.return_value = socket
    monkeypatch.setattr(binance, "BinanceSocketManager", Mock(side_effect=managers))
    streams = asyncio.create_task(task.task(("BTCUSDT", "ETHUSDT")))
    try:
        assert await asyncio.wait_for(asyncio.to_thread(started.wait, 2), 3)
        assert task._received == 200
        assert all(socket.recv.await_count == 101 for socket in sockets)
        assert published == []
        release.set()
        await asyncio.wait_for(task._pending.join(), 3)
    finally:
        release.set()
        streams.cancel()
        await asyncio.gather(streams, return_exceptions=True)
    assert len(published) == 200
    assert len(set(worker_threads)) == 1
    assert worker_threads[0] != threading.get_ident()
    for client in clients:
        client.close_connection.assert_awaited_once()


@pytest.mark.asyncio
async def test_pending_queue_applies_backpressure_instead_of_growing(task, monkeypatch):
    task._pending = asyncio.Queue(maxsize=2)
    client = make_client()
    socket = make_socket({"t": 1}, {"t": 2}, {"t": 3})
    monkeypatch.setattr(binance.AsyncClient, "create", AsyncMock(return_value=client))
    manager = Mock()
    manager.trade_socket.return_value = socket
    monkeypatch.setattr(binance, "BinanceSocketManager", Mock(return_value=manager))
    stream = asyncio.create_task(task.process("BTCUSDT"))
    try:
        await asyncio.sleep(0)
        assert task._pending.qsize() == 2
        assert task._received == 2
        assert socket.recv.await_count == 3
    finally:
        stream.cancel()
        await asyncio.gather(stream, return_exceptions=True)
    client.close_connection.assert_awaited_once()
