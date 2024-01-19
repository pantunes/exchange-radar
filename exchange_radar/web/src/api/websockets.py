from starlette.websockets import WebSocket, WebSocketDisconnect

from exchange_radar.web.src.manager import (
    ConnectionTradesDolphinsManager,
    ConnectionTradesManager,
    ConnectionTradesOctopusesManager,
    ConnectionTradesWhalesManager,
)
from exchange_radar.web.src.serializers.decorators import validate
from exchange_radar.web.src.serializers.http import ParamsInputSerializer

manager_trades = ConnectionTradesManager.get_instance()
manager_trades_dolphins = ConnectionTradesDolphinsManager.get_instance()
manager_trades_octopuses = ConnectionTradesOctopusesManager.get_instance()
manager_trades_whales = ConnectionTradesWhalesManager.get_instance()


@validate(serializer=ParamsInputSerializer)  # pragma: no cover
async def trades(websocket: WebSocket, data: ParamsInputSerializer):
    await manager_trades.connect(websocket, data.coin)
    try:
        while True:
            await websocket.receive_json()
    except WebSocketDisconnect:
        manager_trades.disconnect(websocket, data.coin)


@validate(serializer=ParamsInputSerializer)  # pragma: no cover
async def trades_whales(websocket: WebSocket, data: ParamsInputSerializer):
    await manager_trades_whales.connect(websocket, data.coin)
    try:
        while True:
            await websocket.receive_json()
    except WebSocketDisconnect:
        manager_trades_whales.disconnect(websocket, data.coin)


@validate(serializer=ParamsInputSerializer)  # pragma: no cover
async def trades_dolphins(websocket: WebSocket, data: ParamsInputSerializer):
    await manager_trades_dolphins.connect(websocket, data.coin)
    try:
        while True:
            await websocket.receive_json()
    except WebSocketDisconnect:
        manager_trades_dolphins.disconnect(websocket, data.coin)


@validate(serializer=ParamsInputSerializer)  # pragma: no cover
async def trades_octopuses(websocket: WebSocket, data: ParamsInputSerializer):
    await manager_trades_octopuses.connect(websocket, data.coin)
    try:
        while True:
            await websocket.receive_json()
    except WebSocketDisconnect:
        manager_trades_octopuses.disconnect(websocket, data.coin)
