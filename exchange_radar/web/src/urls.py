from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles

from exchange_radar.web.src.views.http import (
    FeedBase,
    FeedDolphins,
    FeedOctopuses,
    FeedWhales,
    IndexBase,
    IndexDolphins,
    IndexOctopuses,
    IndexWhales,
)
from exchange_radar.web.src.views.websockets import (
    trades,
    trades_dolphins,
    trades_octopuses,
    trades_whales,
)

routes = [
    # Preferably should be served by a load-balancer and not this web-app
    Mount(
        "/static",
        StaticFiles(directory="./exchange_radar/web/static"),
        name="static",
    ),
    # general
    Route("/", endpoint=IndexBase),
    Route("/{coin:str}", endpoint=IndexBase),
    Route("/feed/{coin:str}", endpoint=FeedBase),
    WebSocketRoute("/trades/{coin:str}", endpoint=trades),
    # whales
    Route("/{coin:str}/whales", endpoint=IndexWhales),
    Route("/feed/{coin:str}/whales", endpoint=FeedWhales),
    WebSocketRoute("/trades/{coin:str}/whales", endpoint=trades_whales),
    # dolphins
    Route("/{coin:str}/dolphins", endpoint=IndexDolphins),
    Route("/feed/{coin:str}/dolphins", endpoint=FeedDolphins),
    WebSocketRoute("/trades/{coin:str}/dolphins", endpoint=trades_dolphins),
    # Octopuses
    Route("/{coin:str}/octopuses", endpoint=IndexOctopuses),
    Route("/feed/{coin:str}/octopuses", endpoint=FeedOctopuses),
    WebSocketRoute("/trades/{coin:str}/octopuses", endpoint=trades_octopuses),
]
