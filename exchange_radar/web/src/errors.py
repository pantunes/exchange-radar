from starlette.exceptions import WebSocketException
from starlette.responses import JSONResponse
from starlette.templating import Jinja2Templates
from starlette.websockets import WebSocket

from exchange_radar import __version__
from exchange_radar.web.src.api.http import REST_ENDPOINTS
from exchange_radar.web.src.settings import base as settings

templates = Jinja2Templates(directory=settings.TEMPLATES_DIR)


async def http_validation_error(request, exc):
    if request.scope["endpoint"] in REST_ENDPOINTS:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    context = {"error_message": exc.detail, "version": __version__}
    return templates.TemplateResponse(request, "error.j2", context=context, status_code=exc.status_code)


async def websocket_validation_error(websocket: WebSocket, _: WebSocketException):
    await websocket.close(code=1008)
