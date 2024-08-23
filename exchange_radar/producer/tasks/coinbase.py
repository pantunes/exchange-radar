import asyncio
import logging
from typing import override

from copra.websocket import Channel, Client

from exchange_radar.producer.publisher import publish
from exchange_radar.producer.serializers.coinbase import CoinbaseTradeSerializer
from exchange_radar.producer.tasks.base import Task

logger = logging.getLogger(__name__)


class CoinbaseTradesTask(Task):
    @override
    async def task(self, symbols: tuple[str, ...]):
        await asyncio.gather(self.process(symbols))

    @override
    async def process(self, symbol_or_symbols: str | tuple):
        class CustomClient(Client):
            def on_message(self, message):
                match message:
                    case {"type": "subscriptions"}:
                        pass
                    case _:
                        try:
                            data = CoinbaseTradeSerializer(**message)
                            publish(data)
                        except Exception as error:
                            logger.error(f"ERROR: {error}")

        CustomClient(
            self.loop,
            channels=Channel("matches", list(symbol_or_symbols)),
            feed_url="wss://ws-feed.exchange.coinbase.com:443",
        )

        while True:
            await asyncio.sleep(self.ITER_SLEEP)
