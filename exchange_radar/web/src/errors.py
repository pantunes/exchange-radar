from starlette.responses import JSONResponse
from starlette.templating import Jinja2Templates

from exchange_radar.web.src.endpoints.http import (
    FeedBase,
    FeedDolphins,
    FeedOctopuses,
    FeedWhales,
    Stats,
)

templates = Jinja2Templates(directory="/app/exchange_radar/web/templates")


async def exc_handler(request, exc):
    if request.scope["endpoint"] in (
        FeedBase,
        FeedWhales,
        FeedDolphins,
        FeedOctopuses,
        Stats,
    ):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    context = {"error_message": exc.detail}
    return templates.TemplateResponse(request, "error.j2", context=context, status_code=exc.status_code)
