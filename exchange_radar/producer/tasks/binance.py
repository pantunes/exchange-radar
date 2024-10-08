import asyncio
import logging
from typing import override

from binance import AsyncClient, BinanceSocketManager, exceptions

from exchange_radar.producer.publisher import publish
from exchange_radar.producer.serializers.binance import BinanceTradeSerializer
from exchange_radar.producer.tasks.base import Task

logger = logging.getLogger(__name__)


class BinanceTradesTask(Task):
    @override
    async def process(self, symbol_or_symbols: str | tuple):
        while True:
            try:
                async_client = await AsyncClient.create()
                break
            except exceptions.BinanceAPIException as error:
                logger.error(f"ERROR: {error}")
                logger.error(f"Trying again in {self.ITER_SLEEP} seconds...")
                await asyncio.sleep(self.ITER_SLEEP)

        while True:
            binance_manager = BinanceSocketManager(async_client)

            async with binance_manager.trade_socket(symbol_or_symbols) as ts:
                while True:
                    res = await ts.recv()
                    try:
                        data = BinanceTradeSerializer(**res)
                        publish(data)
                    except Exception as error:
                        logger.error(f"GENERAL ERROR: {error}")
                        logger.error(f"Trying again in {self.ITER_SLEEP} seconds...")
                        await asyncio.sleep(self.ITER_SLEEP)
                        break
