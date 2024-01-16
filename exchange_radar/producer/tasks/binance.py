import asyncio
import logging

from binance import AsyncClient, BinanceSocketManager, exceptions

from exchange_radar.producer.publisher import publish
from exchange_radar.producer.serializers.binance import BinanceTradeSerializer
from exchange_radar.producer.tasks.base import Task

logger = logging.getLogger(__name__)


ITER_SLEEP = 10.0


class BinanceTradesTask(Task):
    async def process(self, symbol_or_symbols: str | tuple):
        while True:
            try:
                async_client = await AsyncClient.create()
                break
            except exceptions.BinanceAPIException as error:
                logger.error(f"ERROR: {error}")
                logger.error(f"Trying again in {ITER_SLEEP} seconds...")
                await asyncio.sleep(ITER_SLEEP)

        binance_manager = BinanceSocketManager(async_client)

        async with binance_manager.trade_socket(symbol_or_symbols) as ts:
            while True:
                res = await ts.recv()
                try:
                    data = BinanceTradeSerializer(**res)
                    publish(data)
                except Exception as error:
                    logger.error(f"GENERAL ERROR: {error}")
