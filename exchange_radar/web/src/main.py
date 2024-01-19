import contextlib
import logging

from starlette.applications import Starlette

from exchange_radar.web.src.errors import exc_handler
from exchange_radar.web.src.settings import base as settings
from exchange_radar.web.src.tasks.sync_cache import sync_cache
from exchange_radar.web.src.urls.endpoints import routes as routes_endpoints
from exchange_radar.web.src.urls.views import routes as routes_views

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


exception_handlers = {
    400: exc_handler,
}

routes = routes_views + routes_endpoints


@contextlib.asynccontextmanager
async def lifespan(app: Starlette):  # noqa
    logger.info("START Lifespan")
    sync_cache()
    yield
    logger.info("END Lifespan")


app = Starlette(debug=settings.DEBUG, routes=routes, exception_handlers=exception_handlers, lifespan=lifespan)
