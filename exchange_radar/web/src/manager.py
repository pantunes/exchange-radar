import logging
from collections import defaultdict

import websockets
from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Singleton:
    @classmethod
    def get_instance(cls):
        if cls._self is None:  # noqa
            cls._self = cls()
        return cls._self  # noqa


class ConnectionTradesManager(Singleton):  # pragma: no cover
    _self = None

    def __str__(self):
        return type(self).__name__

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, coin: str):
        await websocket.accept()
        self.active_connections[coin].append(websocket)
        logger.info(f"Num. active connections {self} {coin}: {len(self.active_connections[coin])}")

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
