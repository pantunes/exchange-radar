import asyncio
import gzip
import json
import threading
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from websockets.asyncio.server import serve

from exchange_radar.producer import batching, models
from exchange_radar.producer.tasks import buffered, bybit, htx, okx
from exchange_radar.producer.tests.test_batching import real_redis  # noqa: F401

CLASSES = [htx.HtxTradesTask, bybit.BybitTradesTask, okx.OkxTradesTask]


def trade(task, number=1, symbol="BTC", **kwargs):
    if isinstance(task, htx.HtxTradesTask):
        return {
            "channel": f"market.{symbol.lower()}usdt.trade.detail",
            "amount": "0.01",
            "price": "2000",
            "ts": 1672515782136,
            "direction": "buy",
            "id": number,
            **kwargs,
        }
    if isinstance(task, bybit.BybitTradesTask):
        return {
            "s": symbol + "USDT",
            "p": "2000",
            "v": "0.01",
            "T": 1672515782136,
            "S": "Buy",
            "i": str(number),
            **kwargs,
        }
    return {
        "instId": symbol + "-USDT",
        "px": "2000",
        "sz": "0.01",
        "ts": "1672515782136",
        "side": "buy",
        "tradeId": str(number),
        **kwargs,
    }


def frame(task, messages):
    if isinstance(task, htx.HtxTradesTask):
        return gzip.compress(json.dumps({"ch": "market.btcusdt.trade.detail", "tick": {"data": messages}}).encode())
    if isinstance(task, bybit.BybitTradesTask):
        return json.dumps({"topic": "publicTrade.BTCUSDT", "type": "snapshot", "data": messages})
    return json.dumps({"arg": {"channel": "trades-all", "instId": "BTC-USDT"}, "data": messages})


def socket(*messages):
    ws = MagicMock()
    ws.__aenter__.return_value = ws
    ws.__aexit__.return_value = False
    ws.recv = AsyncMock(side_effect=[*messages, asyncio.CancelledError()])
    ws.send = AsyncMock()
    return ws


@pytest.fixture(params=CLASSES, ids=["htx", "bybit", "okx"])
def task(request):
    instance = request.param()
    yield instance
    instance._publisher_executor.shutdown(wait=True, cancel_futures=True)
    instance.loop.close()


def test_subscriptions_keep_all_symbols_and_channels(task):
    if isinstance(task, htx.HtxTradesTask):
        assert task.streams(("BTCUSDT", "ETHUSDT")) == ("BTCUSDT", "ETHUSDT")
        assert task.subscriptions("BTCUSDT") == [{"sub": "market.btcusdt.trade.detail"}]
    elif isinstance(task, bybit.BybitTradesTask):
        symbols = tuple(f"COIN{i}USDT" for i in range(23))
        subs = task.subscriptions(symbols)
        assert [len(sub["args"]) for sub in subs] == [10, 10, 3]
        assert [topic for sub in subs for topic in sub["args"]] == [f"publicTrade.{symbol}" for symbol in symbols]
        assert task.subscriptions("BTCUSDT")[0]["args"] == ["publicTrade.BTCUSDT"]
    else:
        assert task.subscriptions(("BTC-USDT", "ETH-USDT")) == [
            {
                "op": "subscribe",
                "args": [
                    {"channel": "trades-all", "instId": "BTC-USDT"},
                    {"channel": "trades-all", "instId": "ETH-USDT"},
                ],
            }
        ]
        assert task.subscriptions("BTC-USDT")[0]["args"] == [{"channel": "trades-all", "instId": "BTC-USDT"}]
    if not isinstance(task, htx.HtxTradesTask):
        assert task.streams(("BTC", "ETH")) == [("BTC", "ETH")]


@pytest.mark.asyncio
async def test_failed_connections_retry_with_a_cap_and_do_not_swallow_cancellation(task, monkeypatch):
    connect = Mock(side_effect=[OSError("offline")] * 5 + [asyncio.CancelledError()])
    monkeypatch.setattr(buffered.websockets, "connect", connect)
    sleep = AsyncMock()
    monkeypatch.setattr(buffered.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        await task.process("BTCUSDT")
    assert [call.args[0] for call in sleep.await_args_list] == [10, 20, 40, 60, 60]
    assert all(call.kwargs["ping_interval"] is None for call in connect.call_args_list)
    assert all(call.kwargs["close_timeout"] == 5 for call in connect.call_args_list)


@pytest.mark.asyncio
async def test_reconnect_closes_previous_socket_and_resubscribes(task, monkeypatch):
    first, second = socket(), socket(frame(task, [trade(task)]))
    first.recv.side_effect = OSError("connection lost")
    connect = Mock(side_effect=[first, second])
    monkeypatch.setattr(buffered.websockets, "connect", connect)
    monkeypatch.setattr(buffered.asyncio, "sleep", AsyncMock())
    with pytest.raises(asyncio.CancelledError):
        await task.process("BTCUSDT")
    assert connect.call_count == 2
    assert task._received == 1
    for ws in (first, second):
        ws.__aexit__.assert_awaited_once()
        assert json.loads(ws.send.await_args_list[0].args[0]) == task.subscriptions("BTCUSDT")[0]


@pytest.mark.asyncio
async def test_silent_and_unwritable_connections_have_deadlines(task):
    ws = socket()

    async def recv():
        await asyncio.sleep(10)

    async def send(message):
        await asyncio.sleep(10)

    ws.recv.side_effect = recv
    ws.send.side_effect = send
    task.RECEIVE_TIMEOUT = task.SEND_TIMEOUT = 0.005
    with pytest.raises(TimeoutError):
        await task.receive(ws)
    with pytest.raises(TimeoutError):
        await task.send(ws, "ping")


@pytest.mark.asyncio
async def test_queue_is_bounded_and_reports_overflow_without_discarding_buffered_trades(task):
    task._pending = asyncio.Queue(maxsize=2)
    with pytest.raises(BufferError, match="unbuffered trades may be lost"):
        task.enqueue([trade(task, i) for i in range(3)])
    assert task._pending.qsize() == task._received == task._peak_queue == 2


@pytest.mark.asyncio
async def test_malformed_trade_lists_are_isolated(task, caplog):
    task.enqueue(None)
    task.enqueue([1, trade(task)])
    assert task._received == 1
    assert "expected a trade list" in caplog.text
    assert "expected an object" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("clock_start", [0.0, 126.01, 126.99, 65534.1])
async def test_event_loop_stalls_are_reported(task, monkeypatch, caplog, clock_start):
    clock = Mock(side_effect=[clock_start, clock_start + 2.5, clock_start + 2.5])
    # Override only the monitor's clock; never patch asyncio's scheduler clock.
    monkeypatch.setattr(buffered.asyncio, "get_running_loop", lambda: Mock(time=clock))
    monkeypatch.setattr(buffered.asyncio, "sleep", AsyncMock(side_effect=[None, asyncio.CancelledError()]))
    with pytest.raises(asyncio.CancelledError):
        await task._monitor_loop()
    assert task._loop_lag == pytest.approx(1.5, rel=0, abs=1e-9)
    assert "socket loop delayed by 1.500s" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["bybit", "okx"])
async def test_control_frames_never_become_trades(kind, caplog):
    task = bybit.BybitTradesTask() if kind == "bybit" else okx.OkxTradesTask()
    frames = [
        {"op": "subscribe", "success": True},
        {"event": "subscribe", "arg": {"channel": "trades-all"}},
        {"op": "ping", "ret_msg": "pong", "success": True},
        {"op": "pong"},
    ]
    ws = socket(
        *[json.dumps(item) for item in frames],
        "pong" if kind == "okx" else json.dumps({"id": "control"}),
        frame(task, [trade(task)]),
    )
    try:
        with pytest.raises(asyncio.CancelledError):
            await task._read_stream(ws)
        assert task._received == 1
        assert not caplog.records
    finally:
        task._publisher_executor.shutdown()
        task.loop.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["bybit", "okx"])
@pytest.mark.parametrize("payload", ["bad json", "[]", b"\xff"])
async def test_malformed_control_frames_do_not_stop_valid_trades(kind, payload, caplog):
    task = bybit.BybitTradesTask() if kind == "bybit" else okx.OkxTradesTask()
    try:
        with pytest.raises(asyncio.CancelledError):
            await task._read_stream(socket(payload, frame(task, [trade(task)])))
        assert task._received == 1
        assert "Invalid" in caplog.text
    finally:
        task._publisher_executor.shutdown()
        task.loop.close()


@pytest.mark.asyncio
async def test_okx_port_retirement_notice_does_not_interrupt_trades_or_heartbeats(caplog):
    task = okx.OkxTradesTask()
    ws = socket(
        json.dumps({"event": "notice", "code": "64010", "msg": "Migrate from port 8443 to 443"}),
        frame(task, [trade(task)]),
        "pong",
        frame(task, [trade(task, number=2)]),
    )
    try:
        with pytest.raises(asyncio.CancelledError):
            await task._read_stream(ws)
        assert task._received == 2
        assert [task._pending.get_nowait()[1]["tradeId"] for _ in range(2)] == ["1", "2"]
        assert "OKX port retirement notice" in caplog.text
    finally:
        task._publisher_executor.shutdown()
        task.loop.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind,payload",
    [
        ("bybit", {"op": "subscribe", "success": False, "ret_msg": "invalid symbol"}),
        ("okx", {"event": "error", "code": "60012", "msg": "invalid symbol"}),
        ("okx", {"event": "notice", "code": "64008", "msg": "service upgrade"}),
    ],
)
async def test_request_errors_and_service_notices_trigger_reconnect(kind, payload):
    task = bybit.BybitTradesTask() if kind == "bybit" else okx.OkxTradesTask()
    try:
        with pytest.raises((RuntimeError, ConnectionError)):
            await task._read_stream(socket(json.dumps(payload)))
    finally:
        task._publisher_executor.shutdown()
        task.loop.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["bybit", "okx"])
@pytest.mark.parametrize("continuous_trades", [False, True])
async def test_missing_pong_times_out_even_if_trades_keep_arriving(kind, continuous_trades):
    task = bybit.BybitTradesTask() if kind == "bybit" else okx.OkxTradesTask()
    task.PING_INTERVAL = task.IDLE_PING_INTERVAL = task.PONG_TIMEOUT = 0.005
    ws = socket()

    async def recv():
        if continuous_trades and ws.send.await_count:
            await asyncio.sleep(0)
            return frame(task, [])
        await asyncio.sleep(10)

    ws.recv.side_effect = recv
    try:
        with pytest.raises(TimeoutError, match="pong not received"):
            await asyncio.wait_for(task._read_stream(ws), 1)
        assert ws.send.await_count == 1
    finally:
        task._publisher_executor.shutdown()
        task.loop.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [1024, 5000])
async def test_bursts_keep_heartbeats_responsive_while_publishing_is_stalled(task, monkeypatch, count):
    started, release = threading.Event(), threading.Event()
    complete, finish = asyncio.Event(), asyncio.Event()
    delivered, pongs, threads, errors = [], [], [], []
    task.PING_INTERVAL = task.IDLE_PING_INTERVAL = 0.01
    task.PONG_TIMEOUT = 0.5
    monkeypatch.setattr(buffered, "TradeStatsStore", Mock())

    class Batch:
        def __init__(self, messages, serializer):
            assert serializer is task.SERIALIZER
            threads.append(threading.get_ident())
            self.messages = messages

        def process(self, store):
            threads.append(threading.get_ident())
            started.set()
            if not release.wait(5):
                raise TimeoutError("test publisher was not released")
            delivered.extend(self.messages)

    monkeypatch.setattr(buffered, "TradeBatch", Batch)
    messages = [trade(task, i) for i in range(count)]

    async def server(ws):
        try:
            await ws.recv()
            if isinstance(task, htx.HtxTradesTask):
                await ws.send(gzip.compress(b'{"status":"ok","subbed":"market.btcusdt.trade.detail"}'))
            elif isinstance(task, bybit.BybitTradesTask):
                await ws.send(json.dumps({"op": "subscribe", "success": True}))
            else:
                await ws.send(json.dumps({"event": "subscribe", "arg": {"channel": "trades-all"}}))
            await ws.send(frame(task, messages))
            assert await asyncio.wait_for(asyncio.to_thread(started.wait, 2), 3)
            for ping in range(4):
                if isinstance(task, htx.HtxTradesTask):
                    await ws.send(gzip.compress(json.dumps({"ping": ping}).encode()))
                    assert json.loads(await asyncio.wait_for(ws.recv(), 0.5)) == {"pong": ping}
                elif isinstance(task, bybit.BybitTradesTask):
                    assert json.loads(await asyncio.wait_for(ws.recv(), 0.5)) == {"op": "ping"}
                    await ws.send(json.dumps({"success": True, "op": "ping", "ret_msg": "pong"}))
                else:
                    assert await asyncio.wait_for(ws.recv(), 0.5) == "ping"
                    await ws.send("pong")
                pongs.append(ping)
            complete.set()
            await finish.wait()
        except Exception as error:
            errors.append(error)
            complete.set()

    async with serve(server, "127.0.0.1", 0) as ws_server:
        task.URL = f"ws://127.0.0.1:{ws_server.sockets[0].getsockname()[1]}"
        symbols = ("BTC-USDT",) if isinstance(task, okx.OkxTradesTask) else ("BTCUSDT",)
        streams = asyncio.create_task(task.task(symbols))
        try:
            await asyncio.wait_for(complete.wait(), 5)
            assert not errors, errors
            assert pongs == list(range(4))
            assert task._received == count
            assert delivered == []
            assert task._peak_queue <= task.MAX_PENDING_TRADES
            release.set()
            await asyncio.wait_for(task._pending.join(), 5)
            assert delivered == messages
            assert len(set(threads)) == 1
            assert threads[0] != threading.get_ident()
        finally:
            release.set()
            streams.cancel()
            await asyncio.gather(streams, return_exceptions=True)
            finish.set()


def test_real_redis_batches_match_legacy_statistics_for_each_exchange(task, real_redis, monkeypatch):  # noqa: F811
    legacy, updated = real_redis(), real_redis()
    kwargs = (
        {"direction": "sell"}
        if isinstance(task, htx.HtxTradesTask)
        else ({"S": "Sell"} if isinstance(task, bybit.BybitTradesTask) else {"side": "sell"})
    )
    messages = [trade(task, 1), trade(task, 2, **kwargs), trade(task, 3, symbol="ETH")]
    monkeypatch.setattr(models, "redis", legacy)
    expected = [task.SERIALIZER(**message).model_dump(mode="json") for message in messages]
    batch = batching.TradeBatch(messages, task.SERIALIZER)
    batching.TradeStatsStore(updated).apply(batch.trades, batch.token)
    assert [data.model_dump(mode="json") for data in batch.trades] == expected
    assert updated.hgetall("2022-12-31") == legacy.hgetall("2022-12-31")
    assert updated.hgetall("COINS") == legacy.hgetall("COINS")
    assert set(updated.hgetall("EXCHANGES")) == {task.EXCHANGE.upper().encode()}
