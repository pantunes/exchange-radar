from starlette.routing import Mount, Route, WebSocketRoute

from exchange_radar.web.src.api.http import (
    FeedBase,
    FeedDolphins,
    FeedOctopuses,
    FeedWhales,
    History,
    Stats,
    Status,
)
from exchange_radar.web.src.api.websockets import (
    trades,
    trades_dolphins,
    trades_octopuses,
    trades_whales,
)

routes: list = [
    Mount(
        "/api",
        routes=[
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
            Route("/history/{coin:str}", endpoint=History),
            Route("/status", endpoint=Status),
        ],
    )
]
