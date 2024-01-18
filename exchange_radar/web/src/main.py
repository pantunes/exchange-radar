from starlette.applications import Starlette

from exchange_radar.web.src.endpoints.http import exc_handler
from exchange_radar.web.src.settings import base as settings
from exchange_radar.web.src.tasks.sync_cache import sync_cache
from exchange_radar.web.src.urls import routes

exception_handlers = {
    400: exc_handler,
}


app = Starlette(debug=settings.DEBUG, routes=routes, exception_handlers=exception_handlers, on_startup=(sync_cache,))
