from starlette.routing import Route, WebSocketRoute

from exchange_radar.web.src.endpoints.http import (
    FeedBase,
    FeedDolphins,
    FeedOctopuses,
    FeedWhales,
    Stats,
)
from exchange_radar.web.src.endpoints.websockets import (
    trades,
    trades_dolphins,
    trades_octopuses,
    trades_whales,
)

routes = [
    # main
    Route("/feed/{coin:str}", endpoint=FeedBase),
    WebSocketRoute("/trades/{coin:str}", endpoint=trades),
    # whales
    Route("/feed/{coin:str}/whales", endpoint=FeedWhales),
    WebSocketRoute("/trades/{coin:str}/whales", endpoint=trades_whales),
    # dolphins
    Route("/feed/{coin:str}/dolphins", endpoint=FeedDolphins),
    WebSocketRoute("/trades/{coin:str}/dolphins", endpoint=trades_dolphins),
    # Octopuses
    Route("/feed/{coin:str}/octopuses", endpoint=FeedOctopuses),
    WebSocketRoute("/trades/{coin:str}/octopuses", endpoint=trades_octopuses),
    # others
    Route("/stats/{coin:str}", endpoint=Stats),
]
