import asyncio
import logging

from copra.websocket import Channel, Client

from exchange_radar.producer.publisher import publish
from exchange_radar.producer.serializers.coinbase import CoinbaseTradeSerializer
from exchange_radar.producer.tasks.base import Task

logger = logging.getLogger(__name__)


ITER_SLEEP = 10.0


class CoinbaseTradesTask(Task):
    async_client = None

    def process(self, symbol_or_symbols: str | tuple):
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

        while True:
            try:
                self.async_client = CustomClient(self.loop, Channel("matches", list(symbol_or_symbols)))
                break
            except Exception as error2:
                logger.error(f"GENERAL ERROR: {error2}")
                logger.error(f"Trying again in {ITER_SLEEP} seconds...")
                asyncio.sleep(ITER_SLEEP)

    def start(self, symbols: tuple[str, ...]):
        logger.info("Starting Task...")
        try:
            self.process(symbol_or_symbols=symbols)
            self.loop.run_forever()
        except KeyboardInterrupt:
            if self.async_client is not None:
                self.loop.run_until_complete(self.async_client.close())
            self.loop.close()
            logger.info("Task was interrupted...")
        finally:
            pass
