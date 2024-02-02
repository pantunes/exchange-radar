import asyncio
import json
import logging

import websockets
from pydantic import ValidationError

from exchange_radar.producer.publisher import publish
from exchange_radar.producer.serializers.bitstamp import BitstampTradeSerializer
from exchange_radar.producer.tasks.base import Task

logger = logging.getLogger(__name__)


ITER_SLEEP = 10.0


class BitstampTradesTask(Task):
    async def process(self, symbol_or_symbols: str | tuple):
        uri = "wss://ws.bitstamp.net"
        message = {"event": "bts:subscribe", "data": {"channel": f"live_trades_{symbol_or_symbols.lower()}"}}

        while True:
            try:
                async with websockets.connect(uri) as ws:
                    await ws.send(json.dumps(message))
                    while True:
                        try:
                            response = json.loads(await ws.recv())
                            response["data"]["channel"] = response["channel"]
                            data = BitstampTradeSerializer(**response["data"])
                            publish(data)
                        except ValidationError:
                            pass
                        except websockets.ConnectionClosed as error:
                            logger.error(f"ERROR(1): {error}")
                            # no close frame received or sent
                            break
                        except Exception as error:
                            logger.error(f"ERROR(2): {error}")
            except Exception as error:
                logger.error(f"GENERAL ERROR: {error}")
            finally:
                logger.error(f"Trying again in {ITER_SLEEP} seconds...")
                await asyncio.sleep(ITER_SLEEP)
