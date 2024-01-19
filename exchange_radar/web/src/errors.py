from starlette.exceptions import HTTPException, WebSocketException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.templating import Jinja2Templates
from starlette.websockets import WebSocket

from exchange_radar.web.src.api.http import REST_ENDPOINTS
from exchange_radar.web.src.exceptions import ERException

templates = Jinja2Templates(directory="/app/exchange_radar/web/templates")


async def http_validation_error(request: Request, exc: HTTPException | ERException) -> Response:
    if request.scope["endpoint"] in REST_ENDPOINTS:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    context = {"error_message": exc.detail}
    return templates.TemplateResponse(request, "error.j2", context=context, status_code=exc.status_code)


async def websocket_validation_error(websocket: WebSocket, _: WebSocketException):
    await websocket.close(code=1008)
