import asyncio
import json
import threading
import time

import pytest
from websockets.asyncio.server import serve

from exchange_radar.producer.tasks import binance


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [500, 5000, 20_000])
async def test_simultaneous_bursts_and_protocol_heartbeats_survive_a_stalled_publisher(monkeypatch, count):
    """Two real sockets remain readable when publishing stops during a burst."""
    start, finish, processed, ponged = (asyncio.Event() for _ in range(4))
    release = threading.Event()
    loop = asyncio.get_running_loop()
    symbols = ("BTCUSDT", "ETHUSDT")
    connections, received, pongs = [], [], []

    async def send_burst(connection):
        symbol = connection.request.path.rsplit("/", 1)[-1].split("@")[0].upper()
        connections.append(symbol)
        if len(connections) == len(symbols):
            start.set()
        await start.wait()
        for trade_id in range(count):
            await connection.send(json.dumps({"e": "trade", "s": symbol, "t": trade_id}))
            if trade_id % 100 == 0:
                await asyncio.sleep(0)
        pong = await connection.ping(symbol.encode())
        await asyncio.wait_for(pong, 5)
        pongs.append(symbol)
        if len(pongs) == len(symbols):
            ponged.set()
        await finish.wait()

    class Batch:
        def __init__(self, messages):
            self.messages = messages

        def process(self, store):
            if not release.wait(10):
                raise TimeoutError("test publisher not released")
            time.sleep(0.001)
            received.extend((message["s"], message["t"]) for message in self.messages)
            if len(received) == len(symbols) * count:
                loop.call_soon_threadsafe(processed.set)

    monkeypatch.setattr(binance, "TradeBatch", Batch)
    monkeypatch.setattr(binance, "TradeStatsStore", lambda: None)
    async with serve(send_burst, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        task = binance.BinanceTradesTask()
        task.URL = f"ws://127.0.0.1:{port}/ws/{{symbol}}@trade"
        worker = asyncio.create_task(task.task(symbols))
        try:
            await asyncio.wait_for(ponged.wait(), 8)
            assert task._received == len(symbols) * count
            assert task._pending_count == len(symbols) * count
            assert received == []
            release.set()
            await asyncio.wait_for(processed.wait(), 10)
            await asyncio.wait_for(task._pending.join(), 2)
            assert task._pending.empty()
            assert task._pending_bytes == task._pending_count == 0
            assert sorted(connections) == sorted(symbols)
            for symbol in symbols:
                assert [trade_id for name, trade_id in received if name == symbol] == list(range(count))
        finally:
            release.set()
            finish.set()
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
            task.loop.close()
