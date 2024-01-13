from starlette.applications import Starlette

from exchange_radar.web.src.settings import base as settings
from exchange_radar.web.src.tasks.sync_cache import sync_cache
from exchange_radar.web.src.urls import routes

app = Starlette(debug=settings.DEBUG, routes=routes, on_startup=(sync_cache,))
