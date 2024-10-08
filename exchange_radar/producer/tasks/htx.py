import asyncio
import gzip
import json
import logging
from typing import override

import websockets

from exchange_radar.producer.publisher import publish
from exchange_radar.producer.serializers.htx import HtxTradeSerializer
from exchange_radar.producer.tasks.base import Task

logger = logging.getLogger(__name__)


class HtxTradesTask(Task):
    @override
    async def process(self, symbol_or_symbols: str | tuple):
        url = "wss://api.huobi.pro/ws"
        message = {"sub": f"market.{symbol_or_symbols.lower()}.trade.detail"}

        while True:
            try:
                async with websockets.connect(url) as ws:
                    await ws.send(json.dumps(message))
                    while True:
                        try:
                            response = json.loads(gzip.decompress(await ws.recv()).decode("utf-8"))
                            if "ping" in response:
                                await ws.send(json.dumps({"pong": response["ping"]}))
                                continue
                            for msg in response["tick"]["data"]:
                                msg["channel"] = response["ch"]
                                data = HtxTradeSerializer(**msg)
                                publish(data)
                        except websockets.ConnectionClosed as error:
                            logger.error(f"ERROR(1): {error}")
                            # no close frame received or sent
                            break
                        except Exception as error:
                            logger.error(f"ERROR(2): {error}")
            except Exception as error:
                logger.error(f"GENERAL ERROR: {error}")
            finally:
                logger.error(f"Trying again in {self.ITER_SLEEP} seconds...")
                await asyncio.sleep(self.ITER_SLEEP)
