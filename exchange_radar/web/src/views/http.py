from starlette.endpoints import HTTPEndpoint
from starlette.responses import JSONResponse
from starlette.templating import Jinja2Templates

from exchange_radar.web.src.manager import (
    ConnectionTradesDolphinsManager,
    ConnectionTradesManager,
    ConnectionTradesOctopusesManager,
    ConnectionTradesWhalesManager,
)
from exchange_radar.web.src.models import Db
from exchange_radar.web.src.settings import base as settings

templates = Jinja2Templates(directory="/app/exchange_radar/web/templates")


manager_trades = ConnectionTradesManager.get_instance()
manager_trades_dolphins = ConnectionTradesDolphinsManager.get_instance()
manager_trades_octopuses = ConnectionTradesOctopusesManager.get_instance()
manager_trades_whales = ConnectionTradesWhalesManager.get_instance()


class IndexBase(HTTPEndpoint):
    http_url = settings.TRADES_HOST_URL
    websocket_url = settings.TRADES_SOCKET_URL
    template_name = "index.html"

    def get(self, request):  # noqa
        coin = request.path_params.get("coin", "BTC")
        context = {
            "request": request,
            "coin": coin,
            "websocket_url": self.websocket_url.format(coin=coin),
            "http_url": self.http_url.format(coin=coin),
            "max_rows": settings.DB_TABLE_MAX_ROWS,
        }
        return templates.TemplateResponse(self.template_name, context=context)


class IndexWhales(IndexBase):
    http_url = settings.TRADES_WHALES_HOST_URL
    websocket_url = settings.TRADES_WHALES_SOCKET_URL
    template_name = "index-whales.html"


class IndexDolphins(IndexBase):
    http_url = settings.TRADES_DOLPHINS_HOST_URL
    websocket_url = settings.TRADES_DOLPHINS_SOCKET_URL
    template_name = "index-dolphins.html"


class IndexOctopuses(IndexBase):
    http_url = settings.TRADES_OCTOPUSES_HOST_URL
    websocket_url = settings.TRADES_OCTOPUSES_SOCKET_URL
    template_name = "index-octopuses.html"


class FeedBase(HTTPEndpoint):
    manager = manager_trades

    def __str__(self):
        return type(self).__name__

    async def post(self, request):  # noqa
        coin = request.path_params["coin"]
        message = await request.json()
        await self.manager.broadcast(message, coin)
        Db.write(cls_name=str(self), coin=coin, message=message)
        return JSONResponse({"r": True}, status_code=201)

    async def get(self, request):  # noqa
        coin = request.path_params["coin"]
        rows = Db.read(cls_name=str(self), coin=coin)
        return JSONResponse({"r": rows}, status_code=200)


class FeedWhales(FeedBase):
    manager = manager_trades_whales


class FeedDolphins(FeedBase):
    manager = manager_trades_dolphins


class FeedOctopuses(FeedBase):
    manager = manager_trades_octopuses
