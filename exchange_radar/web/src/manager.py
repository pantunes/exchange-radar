import logging
from collections import defaultdict

import websockets
from starlette.websockets import WebSocket

from exchange_radar.web.src.settings import base as settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# WebSocket close code 1013 == "Try Again Later".
WS_TRY_AGAIN_LATER = 1013


class Singleton:
    @classmethod
    def get_instance(cls):
        # noinspection PyUnresolvedReferences
        if cls._self is None:
            cls._self = cls()
        # noinspection PyUnresolvedReferences
        return cls._self


class ConnectionTradesManager(Singleton):  # pragma: no cover
    _self = None

    def __str__(self):
        return type(self).__name__

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = defaultdict(list)

    def _total_connections(self) -> int:
        return sum(len(connections) for connections in self.active_connections.values())

    async def connect(self, websocket: WebSocket, coin: str) -> bool:
        if (
            len(self.active_connections[coin]) >= settings.MAX_WS_CONNECTIONS_PER_COIN
            or self._total_connections() >= settings.MAX_WS_CONNECTIONS_TOTAL
        ):
            logger.warning(f"Rejected {self} {coin} connection: limit reached")
            await websocket.close(code=WS_TRY_AGAIN_LATER)
            return False
        await websocket.accept()
        self.active_connections[coin].append(websocket)
        logger.info(f"Num. active connections {self} {coin}: {len(self.active_connections[coin])}")
        return True

    def disconnect(self, websocket: WebSocket, coin: str):
        self.active_connections[coin].remove(websocket)
        logger.info(f"Num. active connections {self} {coin}: {len(self.active_connections[coin])}")

    async def broadcast(self, message: dict, coin: str):
        for connection in self.active_connections[coin]:
            try:
                await connection.send_json(message)
            except (
                websockets.exceptions.ConnectionClosedOK,
                websockets.exceptions.ConnectionClosedError,
            ):
                # connection was closed in the meantime, fine!
                pass


class ConnectionTradesWhalesManager(ConnectionTradesManager):
    _self = None


class ConnectionTradesDolphinsManager(ConnectionTradesManager):
    _self = None


class ConnectionTradesOctopusesManager(ConnectionTradesManager):
    _self = None
