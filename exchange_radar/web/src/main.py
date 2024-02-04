import contextlib
import logging

from starlette.applications import Starlette
from starlette.exceptions import WebSocketException

from exchange_radar.web.src.errors import (
    http_validation_error,
    websocket_validation_error,
)
from exchange_radar.web.src.settings import base as settings
from exchange_radar.web.src.tasks.sync_cache import sync_cache
from exchange_radar.web.src.urls.api import routes as routes_endpoints
from exchange_radar.web.src.urls.schema import routes as routes_schema
from exchange_radar.web.src.urls.views import routes as routes_views

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


exception_handlers = {
    400: http_validation_error,
    WebSocketException: websocket_validation_error,
}

routes = routes_views + routes_schema + routes_endpoints


@contextlib.asynccontextmanager
async def lifespan(app: Starlette):  # noqa
    logger.info("START Lifespan")
    sync_cache()
    yield
    logger.info("END Lifespan")


app = Starlette(debug=settings.DEBUG, routes=routes, exception_handlers=exception_handlers, lifespan=lifespan)
