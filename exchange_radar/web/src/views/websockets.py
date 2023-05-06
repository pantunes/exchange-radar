from starlette.websockets import WebSocket, WebSocketDisconnect

from exchange_radar.web.src.manager import (
    ConnectionTradesDolphinsManager,
    ConnectionTradesManager,
    ConnectionTradesOctopusesManager,
    ConnectionTradesWhalesManager,
)

manager_trades = ConnectionTradesManager.get_instance()
manager_trades_dolphins = ConnectionTradesDolphinsManager.get_instance()
manager_trades_octopuses = ConnectionTradesOctopusesManager.get_instance()
manager_trades_whales = ConnectionTradesWhalesManager.get_instance()


async def trades(websocket: WebSocket):
    coin = websocket.path_params["coin"]
    await manager_trades.connect(websocket, coin)
    try:
        while True:
            await websocket.receive_json()
    except WebSocketDisconnect:
        manager_trades.disconnect(websocket, coin)


async def trades_whales(websocket: WebSocket):
    coin = websocket.path_params["coin"]
    await manager_trades_whales.connect(websocket, coin)
    try:
        while True:
            await websocket.receive_json()
    except WebSocketDisconnect:
        manager_trades_whales.disconnect(websocket, coin)


async def trades_dolphins(websocket: WebSocket):
    coin = websocket.path_params["coin"]
    await manager_trades_dolphins.connect(websocket, coin)
    try:
        while True:
            await websocket.receive_json()
    except WebSocketDisconnect:
        manager_trades_dolphins.disconnect(websocket, coin)


async def trades_octopuses(websocket: WebSocket):
    coin = websocket.path_params["coin"]
    await manager_trades_octopuses.connect(websocket, coin)
    try:
        while True:
            await websocket.receive_json()
    except WebSocketDisconnect:
        manager_trades_octopuses.disconnect(websocket, coin)
