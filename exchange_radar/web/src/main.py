import logging

from starlette.applications import Starlette

from exchange_radar.web.src.settings import base as settings
from exchange_radar.web.src.urls import routes

logging.basicConfig(
    format="%(asctime)s - %(message)s",
    level=logging.INFO if settings.DEBUG else logging.WARNING,
)


app = Starlette(debug=settings.DEBUG, routes=routes)
