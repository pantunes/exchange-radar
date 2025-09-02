import asyncio
import logging
import sys
import threading
from typing import override

from pymexc import spot
from pymexc.proto import ProtoTyping

from exchange_radar.producer.publisher import publish
from exchange_radar.producer.serializers.mexc import MexcTradeSerializer
from exchange_radar.producer.tasks.base import Task

logger = logging.getLogger(__name__)


class MexcTradesTask(Task):
    @override
    async def task(self, symbols: tuple[str]):
        await asyncio.gather(self.process(symbols))

    @override
    async def process(self, symbol_or_symbols: str | tuple):
        def callback(message: ProtoTyping.PublicDealsV3Api):
            try:
                for deal in message.publicAggreDeals.deals:
                    trade_dict = {
                        "s": message.symbol,
                        "p": deal.price,
                        "v": deal.quantity,
                        "t": deal.time,
                        "S": deal.tradeType,
                    }
                    data = MexcTradeSerializer(**trade_dict)
                    publish(data)
            except Exception as error:
                logger.error(f"ERROR: {error}")
                _error = str(error)
                if "socket is already closed" in _error or "sslv3 alert bad record mac" in _error:
                    logger.error("Restarting from callback...")
                    asyncio.run(_start())

        async def _start():
            ws = spot.WebSocket(proto=True)
            ws.deals_stream(callback, list(symbol_or_symbols), interval="10ms")

            while True:
                await asyncio.sleep(self.ITER_SLEEP)

        try:
            await _start()

        except Exception as error2:
            logger.error(f"EXIT ERROR(1): {error2}")
            sys.exit(1)


def thread_exception_handler(args):
    logger.error(f"EXIT ERROR(2): {args.exc_value}")
    sys.exit(1)


threading.excepthook = thread_exception_handler
