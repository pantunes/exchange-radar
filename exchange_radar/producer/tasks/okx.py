import asyncio
import json
import logging
from decimal import Decimal

from exchange_radar.producer.serializers.okx import OkxTradeSerializer
from exchange_radar.producer.tasks.buffered import BufferedTradesTask

logger = logging.getLogger(__name__)


class OkxTradesTask(BufferedTradesTask):
    EXCHANGE = "OKX"
    SERIALIZER = OkxTradeSerializer
    URL = "wss://ws.okx.com:8443/ws/v5/business"
    IDLE_PING_INTERVAL = 20.0
    PONG_TIMEOUT = 20.0

    def subscriptions(self, symbols):
        if isinstance(symbols, str):
            symbols = (symbols,)
        args = [{"channel": "trades-all", "instId": symbol} for symbol in symbols]
        return [{"op": "subscribe", "args": args}]

    async def _read_stream(self, ws):
        loop = asyncio.get_running_loop()
        pong_deadline = None
        while True:
            timeout = self.IDLE_PING_INTERVAL if pong_deadline is None else pong_deadline - loop.time()
            if timeout <= 0:
                raise TimeoutError("OKX pong not received")
            try:
                payload = await self.receive(ws, timeout)
            except TimeoutError:
                if pong_deadline is not None:
                    raise TimeoutError("OKX pong not received") from None
                await self.send(ws, "ping")
                pong_deadline = loop.time() + self.PONG_TIMEOUT
                continue
            if payload in ("pong", b"pong"):
                pong_deadline = None
                continue
            try:
                response = json.loads(payload, parse_float=Decimal)
                if not isinstance(response, dict):
                    raise ValueError("expected a JSON object")
            except (ValueError, UnicodeDecodeError) as error:
                logger.warning("Invalid OKX frame: %s", error)
                continue
            if response.get("event") == "error":
                raise RuntimeError(f"OKX request failed: {response}")
            if response.get("event") == "notice":
                raise ConnectionError(f"OKX service notice: {response}")
            if response.get("arg", {}).get("channel") == "trades-all" and "data" in response:
                self.enqueue(response["data"])
                await asyncio.sleep(0)
