import asyncio
import json
import logging
from decimal import Decimal

from exchange_radar.producer.serializers.bybit import BybitTradeSerializer
from exchange_radar.producer.tasks.buffered import BufferedTradesTask

logger = logging.getLogger(__name__)


class BybitTradesTask(BufferedTradesTask):
    EXCHANGE = "Bybit"
    SERIALIZER = BybitTradeSerializer
    URL = "wss://stream.bybit.com/v5/public/spot"
    PING_INTERVAL = 20.0
    PONG_TIMEOUT = 20.0

    def subscriptions(self, symbols):
        if isinstance(symbols, str):
            symbols = (symbols,)
        return [
            {"op": "subscribe", "args": [f"publicTrade.{symbol}" for symbol in symbols[slice(i, i + 10)]]}
            for i in range(0, len(symbols), 10)
        ]

    async def _read_stream(self, ws):
        loop = asyncio.get_running_loop()
        next_ping = loop.time() + self.PING_INTERVAL
        pong_deadline = None
        while True:
            deadline = next_ping if pong_deadline is None else pong_deadline
            remaining = deadline - loop.time()
            if remaining <= 0:
                if pong_deadline is not None:
                    raise TimeoutError("Bybit pong not received")
                await self.send(ws, json.dumps({"op": "ping"}))
                pong_deadline = loop.time() + self.PONG_TIMEOUT
                continue
            try:
                payload = await self.receive(ws, remaining)
            except TimeoutError:
                continue
            try:
                response = json.loads(payload, parse_float=Decimal)
                if not isinstance(response, dict):
                    raise ValueError("expected a JSON object")
            except (ValueError, UnicodeDecodeError) as error:
                logger.warning("Invalid Bybit frame: %s", error)
                continue
            if response.get("success") is False:
                raise RuntimeError(f"Bybit request failed: {response}")
            if response.get("op") == "pong" or (response.get("op") == "ping" and response.get("ret_msg") == "pong"):
                pong_deadline = None
                next_ping = loop.time() + self.PING_INTERVAL
                continue
            if response.get("topic", "").startswith("publicTrade."):
                self.enqueue(response.get("data"))
                await asyncio.sleep(0)
