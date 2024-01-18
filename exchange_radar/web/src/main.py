from starlette.applications import Starlette

from exchange_radar.web.src.settings import base as settings
from exchange_radar.web.src.tasks.sync_cache import sync_cache
from exchange_radar.web.src.urls.endpoints import routes as routes_endpoints
from exchange_radar.web.src.urls.views import routes as routes_views
from exchange_radar.web.src.views import exc_handler

exception_handlers = {
    400: exc_handler,
}

routes = routes_views + routes_endpoints

app = Starlette(debug=settings.DEBUG, routes=routes, exception_handlers=exception_handlers, on_startup=(sync_cache,))
