import asyncio
import json
import time

import pytest
from websockets.asyncio.server import serve

from exchange_radar.producer.tasks import binance


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [500, 5000])
async def test_simultaneous_bursts_reach_worker_through_real_sdk(monkeypatch, count):
    """Exercise actual SDK buffering with a slow stand-in for Redis/RabbitMQ."""
    start, finish, processed = asyncio.Event(), asyncio.Event(), asyncio.Event()
    loop = asyncio.get_running_loop()
    symbols = ("BTCUSDT", "ETHUSDT")
    connections = []
    received = []

    async def send_burst(connection):
        symbol = connection.request.path.rsplit("/", 1)[-1].split("@")[0].upper()
        connections.append(symbol)
        if len(connections) == len(symbols):
            start.set()
        await start.wait()
        for trade_id in range(count):
            await connection.send(json.dumps({"s": symbol, "t": trade_id}))
        await finish.wait()

    async def create_client():
        # Skip REST initialization; use the real client/session and socket manager.
        return binance.AsyncClient()

    class Batch:
        def __init__(self, messages):
            self.messages = messages

        def process(self, store):
            time.sleep(0.001)
            received.extend((message["s"], message["t"]) for message in self.messages)
            if len(received) == len(symbols) * count:
                loop.call_soon_threadsafe(processed.set)

    monkeypatch.setattr(binance.AsyncClient, "create", create_client)
    monkeypatch.setattr(binance, "TradeBatch", Batch)
    monkeypatch.setattr(binance, "TradeStatsStore", lambda: None)
    async with serve(send_burst, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        monkeypatch.setattr(binance.BinanceSocketManager, "STREAM_URL", f"ws://127.0.0.1:{port}/")
        task = binance.BinanceTradesTask()
        worker = asyncio.create_task(task.task(symbols))
        try:
            await asyncio.wait_for(processed.wait(), 10)
            await asyncio.wait_for(task._pending.join(), 2)
            assert task._received == len(symbols) * count
            assert task._pending.empty()
            assert sorted(connections) == sorted(symbols)
            for symbol in symbols:
                assert [trade_id for name, trade_id in received if name == symbol] == list(range(count))
        finally:
            finish.set()
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
            task.loop.close()
