import asyncio
import json

import pytest
import websockets
from websockets.asyncio.server import serve

from exchange_radar.producer.tests.test_htx import task  # noqa: F401
from exchange_radar.producer.tests.test_htx import (
    frame,
    packed,
    socket,
    stage_frames,
    trade,
)

CHANNEL = "market.ethusdt.trade.detail"
OTHER_CHANNEL = "market.btcusdt.trade.detail"
BASE_TIME = 1672515782000


def row(identity, **kwargs):
    return trade(tradeId=identity, ts=BASE_TIME + identity, **kwargs)


def history(*messages, request=1, channel=CHANNEL, **kwargs):
    return {
        "id": f"htx-recovery-{request}",
        "status": "ok",
        "rep": channel,
        "data": list(messages),
        **kwargs,
    }


async def prime(instance):
    instance._admit_frame(CHANNEL, [row(10)], 200)
    await stage_frames(instance)


async def drain(instance):
    await stage_frames(instance)
    return [instance._pending.get_nowait()[1]["tradeId"] for _ in range(instance._pending.qsize())]


@pytest.mark.asyncio
async def test_recovery_merges_missing_history_with_live_overlap_once_in_order(task, caplog):  # noqa: F811
    await prime(task)
    ws = socket(
        frame(row(13), channel=CHANNEL),
        {"ping": 77},
        history(row(13), row(12), row(11), row(10)),
        frame(row(13), row(14), channel=CHANNEL),
    )
    with pytest.raises(asyncio.CancelledError):
        await task._read_connected_stream(ws, "ETHUSDT")
    assert await drain(task) == [10, 11, 12, 13, 14]
    assert [json.loads(call.args[0]) for call in ws.send.await_args_list] == [
        {"req": CHANNEL, "id": "htx-recovery-1"},
        {"pong": 77},
    ]
    assert task._received == 5
    assert task._held_bytes == task._held_frames == 0
    assert not task._recoveries
    assert "HTX recovery complete" in caplog.text


@pytest.mark.asyncio
async def test_duplicate_ids_are_scoped_to_symbol_and_cache_is_bounded(task):  # noqa: F811
    task.MAX_SEEN_TRADES = 3
    task._admit_frame(CHANNEL, [row(i) for i in range(5)], 500)
    task._admit_frame(CHANNEL, [row(4), row(4)], 200)
    task._admit_frame(OTHER_CHANNEL, [row(4)], 200)
    await stage_frames(task)
    assert task._received == 6
    assert len(task._seen[CHANNEL]) == 3
    assert list(task._seen[OTHER_CHANNEL]) == ["4"]


@pytest.mark.asyncio
async def test_distinct_ids_are_not_discarded_for_being_numerically_smaller(task):  # noqa: F811
    task._admit_frame(CHANNEL, [row(30), row(20), row(30)], 500)
    assert await drain(task) == [30, 20]


@pytest.mark.asyncio
async def test_missing_cursor_metadata_is_explicit_when_reconnecting(task, caplog):  # noqa: F811
    task._admit_frame(CHANNEL, [trade()], 200)
    ws = socket(frame(row(11), channel=CHANNEL))
    with pytest.raises(asyncio.CancelledError):
        await task._read_connected_stream(ws, "ETHUSDT")
    assert "previous trades lacked usable IDs/timestamps" in caplog.text
    assert "gap may remain" in caplog.text
    ws.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_interrupted_recovery_retains_live_frames_for_the_next_connection(task):  # noqa: F811
    await prime(task)
    first = socket()
    first.recv.side_effect = [packed(frame(row(12), channel=CHANNEL)), OSError("disconnected again")]
    with pytest.raises(OSError):
        await task._read_connected_stream(first, "ETHUSDT")
    assert task._held_frames == 1
    assert task._last_trade[CHANNEL][0] == "10"
    second = socket(history(row(12), row(11), row(10), request=2), frame(row(13), channel=CHANNEL))
    with pytest.raises(asyncio.CancelledError):
        await task._read_connected_stream(second, "ETHUSDT")
    assert await drain(task) == [10, 11, 12, 13]
    assert task._held_bytes == task._held_frames == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "rejected", "wrong-channel", "invalid", "invalid-trade", "oversized"])
async def test_history_failure_warns_and_releases_buffered_live_trades(task, caplog, failure):  # noqa: F811
    await prime(task)
    replies = {
        "timeout": TimeoutError(),
        "rejected": history(status="error"),
        "wrong-channel": history(row(10), channel=OTHER_CHANNEL),
        "invalid": history(123),
        "invalid-trade": history(row(10), {"tradeId": 11, "ts": BASE_TIME + 11}),
        "oversized": history(*[row(i) for i in range(301)]),
    }
    ws = socket()
    reply = replies[failure]
    ws.recv.side_effect = [
        packed(frame(row(12), channel=CHANNEL)),
        reply if isinstance(reply, Exception) else packed(reply),
        packed(frame(row(13), channel=CHANNEL)),
        asyncio.CancelledError(),
    ]
    with pytest.raises(asyncio.CancelledError):
        await task._read_connected_stream(ws, "ETHUSDT")
    assert await drain(task) == [10, 12, 13]
    assert "HTX recovery incomplete" in caplog.text
    assert "gap may remain" in caplog.text
    assert not task._recoveries


@pytest.mark.asyncio
async def test_history_window_that_misses_cursor_recovers_available_trades_and_warns(task, caplog):  # noqa: F811
    await prime(task)
    ws = socket(frame(row(14), channel=CHANNEL), history(row(14), row(13)))
    with pytest.raises(asyncio.CancelledError):
        await task._read_connected_stream(ws, "ETHUSDT")
    assert await drain(task) == [10, 13, 14]
    assert "history does not include the previous trade" in caplog.text


@pytest.mark.asyncio
async def test_history_does_not_replay_trades_before_the_connection_cursor(task):  # noqa: F811
    await prime(task)
    ws = socket(history(row(11), row(10), row(9)))
    with pytest.raises(asyncio.CancelledError):
        await task._read_connected_stream(ws, "ETHUSDT")
    assert await drain(task) == [10, 11]


@pytest.mark.asyncio
async def test_stale_history_response_cannot_complete_a_new_recovery(task):  # noqa: F811
    await prime(task)
    ws = socket(history(row(99), request=0), {"ping": 7}, history(row(11), row(10)))
    with pytest.raises(asyncio.CancelledError):
        await task._read_connected_stream(ws, "ETHUSDT")
    assert await drain(task) == [10, 11]
    assert {"pong": 7} in [json.loads(call.args[0]) for call in ws.send.await_args_list]


@pytest.mark.asyncio
async def test_recovery_buffers_share_the_existing_ingress_budget(task):  # noqa: F811
    await prime(task)
    task.MAX_INGRESS_BYTES = 600
    ws = socket()
    ws.recv.side_effect = [packed(frame(row(12), channel=CHANNEL)), OSError("offline")]
    with pytest.raises(OSError):
        await task._read_connected_stream(ws, "ETHUSDT")
    held_bytes = task._held_bytes
    with pytest.raises(BufferError, match="recovery buffer is full"):
        task._hold_frame(CHANNEL, [row(13)], 600)
    with pytest.raises(BufferError, match="ingress buffer is full"):
        task._admit_frame(OTHER_CHANNEL, [row(13)], 600)
    assert task._held_bytes == held_bytes
    assert task._last_trade[CHANNEL][0] == "10"
    task.MAX_INGRESS_BYTES = 10000
    task._finish_recovery(CHANNEL, [row(10), row(11), row(12)])
    assert await drain(task) == [10, 11, 12]


@pytest.mark.asyncio
async def test_failed_ingress_transfer_retains_recovery_state_and_cursor(task):  # noqa: F811
    await prime(task)
    ws = socket()
    ws.recv.side_effect = [packed(frame(row(12), channel=CHANNEL)), OSError("offline")]
    with pytest.raises(OSError):
        await task._read_connected_stream(ws, "ETHUSDT")
    budget = task._held_bytes
    task.MAX_INGRESS_BYTES = 1
    with pytest.raises(BufferError):
        task._finish_recovery(CHANNEL, [row(10), row(11), row(12)])
    assert task._held_bytes == budget
    assert task._held_frames == 1
    assert task._last_trade[CHANNEL][0] == "10"


@pytest.mark.asyncio
async def test_other_symbols_continue_while_one_symbol_waits_for_recovery(task):  # noqa: F811
    await prime(task)
    waiting = socket()
    waiting.recv.side_effect = [packed(frame(row(12), channel=CHANNEL)), OSError("offline")]
    with pytest.raises(OSError):
        await task._read_connected_stream(waiting, "ETHUSDT")
    other = socket(frame(row(20), channel=OTHER_CHANNEL))
    with pytest.raises(asyncio.CancelledError):
        await task._read_connected_stream(other, "BTCUSDT")
    assert await drain(task) == [10, 20]
    other.send.assert_not_awaited()
    assert task._held_frames == 1


@pytest.mark.asyncio
async def test_bad_live_timestamp_cannot_poison_recovery(task):  # noqa: F811
    await prime(task)
    malformed = row(12)
    malformed["ts"] = "invalid"
    ws = socket(frame(malformed, row(13), channel=CHANNEL), history(row(11), row(10)))
    with pytest.raises(asyncio.CancelledError):
        await task._read_connected_stream(ws, "ETHUSDT")
    assert await drain(task) == [10, 12, 11, 13]
    assert not task._recoveries


@pytest.mark.asyncio
async def test_heartbeats_cannot_extend_the_recovery_deadline(task, caplog):  # noqa: F811
    await prime(task)
    task.RECOVERY_TIMEOUT = 0.005
    ws = socket()
    count = 0

    async def receive():
        nonlocal count
        await asyncio.sleep(0.002)
        count += 1
        if count > 10:
            raise asyncio.CancelledError()
        return packed({"ping": count})

    ws.recv.side_effect = receive
    with pytest.raises(asyncio.CancelledError):
        await task._read_connected_stream(ws, "ETHUSDT")
    assert "history request timed out" in caplog.text
    assert not task._recoveries


@pytest.mark.asyncio
async def test_real_socket_keeps_heartbeats_responsive_while_waiting_for_history(task):  # noqa: F811
    await prime(task)
    ready, finish = asyncio.Event(), asyncio.Event()
    errors = []

    async def server(ws):
        try:
            request = json.loads(await ws.recv())
            await ws.send(packed(frame(row(13), channel=CHANNEL)))
            await ws.send(packed({"ping": 42}))
            assert json.loads(await asyncio.wait_for(ws.recv(), 1)) == {"pong": 42}
            assert task._held_frames == 1
            await ws.send(packed(history(row(13), row(12), row(11), row(10), id=request["id"])))
            await ws.send(packed(frame(row(13), row(14), channel=CHANNEL)))
            ready.set()
            await finish.wait()
        except Exception as error:
            errors.append(error)
            ready.set()

    async with serve(server, "127.0.0.1", 0) as listener:
        port = listener.sockets[0].getsockname()[1]
        async with websockets.connect(f"ws://127.0.0.1:{port}", ping_interval=None) as ws:
            reader = asyncio.create_task(task._read_connected_stream(ws, "ETHUSDT"))
            try:
                await asyncio.wait_for(ready.wait(), 3)
                for _ in range(100):
                    if task._received == 5 or reader.done():
                        break
                    await asyncio.sleep(0.01)
                assert not errors
                assert task._received == 5
                assert await drain(task) == [10, 11, 12, 13, 14]
            finally:
                reader.cancel()
                await asyncio.gather(reader, return_exceptions=True)
                finish.set()
