from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from exchange_radar.web.src.views import (
    History,
    IndexBase,
    IndexDolphins,
    IndexOctopuses,
    IndexWhales,
)

routes: list = [
    # Preferably should be served by a load-balancer and not this web-app
    Mount("/static", app=StaticFiles(directory="./exchange_radar/web/static"), name="static"),
    # main
    Route("/", endpoint=IndexBase),
    Route("/{coin:str}", endpoint=IndexBase),
    # whales
    Route("/{coin:str}/whales", endpoint=IndexWhales),
    # dolphins
    Route("/{coin:str}/dolphins", endpoint=IndexDolphins),
    # Octopuses
    Route("/{coin:str}/octopuses", endpoint=IndexOctopuses),
    # history
    Route("/history/{coin:str}", endpoint=History),
]
