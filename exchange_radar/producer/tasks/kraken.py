import asyncio
import logging
from typing import override

from exchange_radar.producer.publisher import publish
from exchange_radar.producer.serializers.kraken import KrakenTradeSerializer
from exchange_radar.producer.tasks.base import Task
from exchange_radar.producer.tasks.libs.kraken import WSKrakenClient, WSKrakenInMsg

logger = logging.getLogger(__name__)


class KrakenTradesTask(Task):
    @override
    async def task(self, symbols: tuple[str]):
        await asyncio.gather(self.process(symbols))

    @override
    async def process(self, symbol_or_symbols: str | tuple):
        async def recv_msgs(websocket):
            async for msg in websocket:
                await handle_msg(WSKrakenInMsg(msg))

        async def handle_msg(msg: WSKrakenInMsg):
            match msg.payload:
                case {"event": "heartbeat"}:
                    pass
                case {"event": "systemStatus"}:
                    pass
                case {"event": "subscriptionStatus"}:
                    pass
                case _:
                    try:
                        _, trades, _, symbol = msg.payload
                        for trade in trades:
                            price, volume, time, side, order_type, misc = trade
                            data = KrakenTradeSerializer(
                                symbol=symbol,
                                price=price,
                                quantity=volume,
                                trade_time=time,
                                side=side,
                            )
                            publish(data)
                    except Exception as error:
                        logger.error(f"ERROR: {error}")

        async def _start():
            async with WSKrakenClient(open_auth_socket=False) as client:
                recv_task = asyncio.create_task(recv_msgs(client.websocket))
                await client.subscribe_trade(pair=list(symbol_or_symbols))
                await recv_task

        while True:
            try:
                await _start()

            except Exception as error2:
                logger.error(f"GENERAL ERROR: {error2}")
                _error = str(error2)
                if "please reconnect" in _error:
                    logger.error("Restarting...")
                    continue

            finally:
                logger.error(f"Trying again in {self.ITER_SLEEP} seconds...")
                await asyncio.sleep(self.ITER_SLEEP)
