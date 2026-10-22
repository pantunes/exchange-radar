import asyncio
import gzip
import json
import threading
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from pydantic import ValidationError
from websockets.asyncio.server import serve

from exchange_radar.producer import batching, models
from exchange_radar.producer.serializers.htx import HtxTradeSerializer
from exchange_radar.producer.tasks import buffered, htx
from exchange_radar.producer.tests.test_batching import (  # noqa: F401
    mock_store,
    real_redis,
)


def trade(amount="0.008428868868868868", **kwargs):
    return {"amount": amount, "price": "2000", "ts": 1672515782136, "direction": "buy", **kwargs}


def frame(*messages, channel="market.btcusdt.trade.detail"):
    return {"ch": channel, "tick": {"data": list(messages)}}


def packed(message):
    return gzip.compress(json.dumps(message).encode())


def socket(*messages):
    ws = MagicMock()
    ws.__aenter__.return_value = ws
    ws.__aexit__.return_value = False
    ws.recv = AsyncMock(side_effect=[*[packed(message) for message in messages], asyncio.CancelledError()])
    ws.send = AsyncMock()
    return ws


@pytest.fixture
def task():
    instance = htx.HtxTradesTask()
    yield instance
    instance._publisher_executor.shutdown(wait=True, cancel_futures=True)
    instance.loop.close()


async def stage_frames(task):
    worker = asyncio.create_task(task._stage_frames())
    try:
        await asyncio.wait_for(task._frames.join(), 1)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.parametrize("amount", ["0.008428868868868868", "2.835671342685e-06", "0.000364729458917835"])
def test_high_precision_trades_are_preserved(amount):
    data = HtxTradeSerializer(_defer_stats=True, channel="market.btcusdt.trade.detail", **trade(amount))
    assert data.quantity == Decimal(amount)
    assert data.price == Decimal("2000")
    assert data.exchange == "HTX"
    assert data.is_seller is False


@pytest.mark.parametrize("field", ["price", "amount"])
@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity"])
def test_invalid_numbers_remain_rejected(field, value):
    with pytest.raises(ValidationError):
        HtxTradeSerializer(_defer_stats=True, channel="market.btcusdt.trade.detail", **trade(**{field: value}))


def test_high_precision_price_is_preserved():
    data = HtxTradeSerializer(
        _defer_stats=True, channel="market.btcusdt.trade.detail", **trade(price="0.000000000123456789")
    )
    assert data.price == Decimal("0.000000000123456789")


@pytest.mark.asyncio
async def test_acknowledgements_and_control_frames_do_not_become_trades(task, caplog):
    ws = socket(
        {"status": "ok", "subbed": "market.btcusdt.trade.detail"},
        {"id": "control"},
        {"ping": 12345},
        frame(trade()),
    )
    with pytest.raises(asyncio.CancelledError):
        await task._read_stream(ws)
    await stage_frames(task)
    ws.send.assert_awaited_once_with('{"pong": 12345}')
    assert task._received == 1
    assert task._pending.get_nowait()[1] == {**trade(), "channel": "market.btcusdt.trade.detail"}
    assert not caplog.records


@pytest.mark.asyncio
async def test_decimal_json_decode_does_not_pass_through_binary_float(task):
    ws = socket()
    ws.recv.side_effect = [
        gzip.compress(b'{"ch":"market.btcusdt.trade.detail","tick":{"data":[{"amount":0.008428868868868868}]}}'),
        asyncio.CancelledError(),
    ]
    with pytest.raises(asyncio.CancelledError):
        await task._read_stream(ws)
    await stage_frames(task)
    assert task._pending.get_nowait()[1]["amount"] == Decimal("0.008428868868868868")


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [b"bad gzip", "bad json", "[]", packed({"tick": None}), packed(frame(1))])
async def test_bad_frames_do_not_prevent_later_heartbeats(task, payload, caplog):
    ws = socket()
    ws.recv.side_effect = [payload, packed({"ping": 42}), packed(frame(trade())), asyncio.CancelledError()]
    with pytest.raises(asyncio.CancelledError):
        await task._read_stream(ws)
    await stage_frames(task)
    ws.send.assert_awaited_once_with('{"pong": 42}')
    assert task._received == 1
    assert "Invalid HTX" in caplog.text


@pytest.mark.asyncio
async def test_subscription_errors_are_reported(task):
    with pytest.raises(RuntimeError, match="invalid symbol"):
        await task._read_stream(socket({"status": "error", "err-msg": "invalid symbol"}))


@pytest.mark.asyncio
async def test_full_queue_retains_frames_and_answers_later_heartbeats(task):
    task._pending = asyncio.Queue(maxsize=2)
    ws = socket(frame(trade(), trade(), trade()), {"ping": 42})
    with pytest.raises(asyncio.CancelledError):
        await task._read_stream(ws)
    assert task._received == task._frame_trades == 3
    assert task._frames.qsize() == 1
    ws.send.assert_awaited_once_with('{"pong": 42}')


@pytest.mark.asyncio
async def test_disconnect_reconnects_without_treating_cancellation_as_a_failure(task, monkeypatch):
    first, second = socket(), socket(frame(trade()))
    first.recv.side_effect = OSError("heartbeat expired")
    connect = Mock(side_effect=[first, second])
    monkeypatch.setattr(buffered.websockets, "connect", connect)
    sleep = AsyncMock()
    monkeypatch.setattr(buffered.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        await task.process("BTCUSDT")
    await stage_frames(task)
    assert connect.call_count == 2
    assert [call.args[0] for call in sleep.await_args_list] == [10.0, 0]
    for ws in (first, second):
        ws.__aexit__.assert_awaited_once()
        assert json.loads(ws.send.await_args.args[0]) == {"sub": "market.btcusdt.trade.detail"}
    assert task._received == 1


@pytest.mark.asyncio
async def test_repeated_connection_failures_back_off_with_a_limit(task, monkeypatch):
    monkeypatch.setattr(
        buffered.websockets, "connect", Mock(side_effect=[OSError("offline")] * 5 + [asyncio.CancelledError()])
    )
    sleep = AsyncMock()
    monkeypatch.setattr(buffered.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        await task.process("BTCUSDT")
    assert [call.args[0] for call in sleep.await_args_list] == [10.0, 20.0, 40.0, 60.0, 60.0]


@pytest.mark.asyncio
async def test_retry_delay_resets_after_stable_connection(task, monkeypatch):
    first, second = socket(), socket()
    first.recv.side_effect = second.recv.side_effect = OSError("lost")
    monkeypatch.setattr(buffered.websockets, "connect", Mock(side_effect=[first, second, asyncio.CancelledError()]))
    monkeypatch.setattr(buffered, "monotonic", Mock(side_effect=[0, 1, 2, 100]))
    sleep = AsyncMock()
    monkeypatch.setattr(buffered.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        await task.process("BTCUSDT")
    assert [call.args[0] for call in sleep.await_args_list] == [10.0, 10.0]


@pytest.mark.asyncio
@pytest.mark.parametrize("count,sizes", [(53, [50, 3]), (1, [1])])
async def test_worker_flushes_bounded_batches_and_keeps_order(task, monkeypatch, count, sizes, caplog):
    batches, threads = [], []
    monkeypatch.setattr(buffered, "TradeStatsStore", Mock())

    class Batch:
        def __init__(self, messages, serializer):
            assert serializer is HtxTradeSerializer
            threads.append(threading.get_ident())
            self.messages = messages

        def process(self, store):
            threads.append(threading.get_ident())
            batches.append(self.messages)

    monkeypatch.setattr(buffered, "TradeBatch", Batch)
    for i in range(count):
        task._pending.put_nowait((0, {"id": i}))
    task.REPORT_INTERVAL = 0
    worker = asyncio.create_task(task._publish_batches())
    try:
        await asyncio.wait_for(task._pending.join(), 2)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
    assert [len(batch) for batch in batches] == sizes
    assert [message["id"] for batch in batches for message in batch] == list(range(count))
    assert "HTX throughput:" in caplog.text
    assert len(set(threads)) == 1
    assert threads[0] != threading.get_ident()


@pytest.mark.asyncio
async def test_batch_failure_retries_before_later_trades(task, monkeypatch):
    task.BATCH_SIZE = 1
    monkeypatch.setattr(buffered, "TradeStatsStore", Mock())
    sleep = AsyncMock()
    monkeypatch.setattr(buffered.asyncio, "sleep", sleep)
    attempts = []

    class Batch:
        def __init__(self, messages, serializer):
            self.message = messages[0]

        def process(self, store):
            attempts.append(self.message["id"])
            if len(attempts) < 3:
                raise ConnectionError("temporary failure")

    monkeypatch.setattr(buffered, "TradeBatch", Batch)
    for i in (1, 2):
        task._pending.put_nowait((0, {"id": i}))
    worker = asyncio.create_task(task._publish_batches())
    try:
        await asyncio.wait_for(task._pending.join(), 2)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
    assert attempts == [1, 1, 1, 2]
    assert [call.args[0] for call in sleep.await_args_list] == [1.0, 2.0]


def test_invalid_trade_does_not_discard_other_trades_and_retry_preserves_statistics(monkeypatch):
    store, script = mock_store(["1", "1", None, 1, None], ["3", "1", "2", 1, 1])
    channel = "market.btcusdt.trade.detail"
    batch = batching.TradeBatch(
        [
            {"channel": channel},
            {"channel": channel, **trade(amount="-1")},
            {"channel": channel, **trade(amount="1")},
            {"channel": channel, **trade(amount="2", direction="sell")},
        ],
        HtxTradeSerializer,
    )
    publish = Mock(side_effect=[None, ConnectionError("lost"), None])
    monkeypatch.setattr(batching, "publish", publish)
    with pytest.raises(ConnectionError):
        batch.process(store)
    batch.process(store)
    assert len(batch.trades) == 2
    assert [call.args[0].quantity for call in publish.call_args_list] == [Decimal(1), Decimal(2), Decimal(2)]
    assert script.call_count == 1
    assert batch.trades[-1].volume == 3.0
    assert batch.trades[-1].number_trades == (1, 1)
    assert batch.trades[-1].exchange == "HTX"
    assert [entry["id"] for entry in json.loads(script.call_args.kwargs["args"][0])] == [False, False]


def test_real_redis_htx_batches_match_legacy_statistics(real_redis, monkeypatch):  # noqa: F811
    legacy, updated = real_redis(), real_redis()
    messages = [
        {"channel": "market.btcusdt.trade.detail", **trade()},
        {"channel": "market.btcusdt.trade.detail", **trade(direction="sell")},
        {"channel": "market.ethusdt.trade.detail", **trade(amount="2.835671342685e-06")},
    ]
    monkeypatch.setattr(models, "redis", legacy)
    expected = [HtxTradeSerializer(**message).model_dump(mode="json") for message in messages]
    batch = batching.TradeBatch(messages, HtxTradeSerializer)
    batching.TradeStatsStore(updated).apply(batch.trades, batch.token)
    assert [data.model_dump(mode="json") for data in batch.trades] == expected
    assert set(updated.hgetall("EXCHANGES")) == {b"HTX"}
    assert updated.hgetall("COINS") == legacy.hgetall("COINS")
    assert updated.hgetall(batch.trades[0]._name) == legacy.hgetall(batch.trades[0]._name)


@pytest.mark.asyncio
async def test_real_compressed_socket_replies_to_heartbeats_during_blocked_publish(task, monkeypatch):
    started, release = threading.Event(), threading.Event()
    pongs, received, worker_threads = [], [], []
    finish, complete = asyncio.Event(), asyncio.Event()
    monkeypatch.setattr(buffered, "TradeStatsStore", Mock())

    class Batch:
        def __init__(self, messages, serializer):
            worker_threads.append(threading.get_ident())
            self.messages = messages

        def process(self, store):
            worker_threads.append(threading.get_ident())
            started.set()
            if not release.wait(5):
                raise TimeoutError("publisher was not released")
            received.extend(self.messages)

    monkeypatch.setattr(buffered, "TradeBatch", Batch)

    async def server(connection):
        subscription = json.loads(await connection.recv())["sub"]
        await connection.send(packed({"status": "ok", "subbed": subscription}))
        await connection.send(packed(frame(*[trade(id=i) for i in range(100)], channel=subscription)))
        assert await asyncio.wait_for(asyncio.to_thread(started.wait, 2), 3)
        for ping in range(4):
            await connection.send(packed({"ping": ping}))
            pongs.append(json.loads(await asyncio.wait_for(connection.recv(), 0.5)))
        complete.set()
        await finish.wait()

    async with serve(server, "127.0.0.1", 0) as ws_server:
        port = ws_server.sockets[0].getsockname()[1]
        task.URL = f"ws://127.0.0.1:{port}"
        streams = asyncio.create_task(task.task(("BTCUSDT",)))
        try:
            await asyncio.wait_for(complete.wait(), 5)
            assert task._received == 100
            assert received == []
            assert pongs == [{"pong": i} for i in range(4)]
            release.set()
            await asyncio.wait_for(task._pending.join(), 3)
            assert [message["id"] for message in received] == list(range(100))
            assert len(set(worker_threads)) == 1
            assert worker_threads[0] != threading.get_ident()
        finally:
            release.set()
            streams.cancel()
            await asyncio.gather(streams, return_exceptions=True)
            finish.set()
