from starlette.endpoints import HTTPEndpoint
from starlette.responses import JSONResponse
from starlette.templating import Jinja2Templates

from exchange_radar.web.src.manager import (
    ConnectionTradesDolphinsManager,
    ConnectionTradesManager,
    ConnectionTradesOctopusesManager,
    ConnectionTradesWhalesManager,
)
from exchange_radar.web.src.models.tinydb import Db
from exchange_radar.web.src.serializers.stats import StatsSerializer
from exchange_radar.web.src.settings import base as settings
from exchange_radar.web.src.utils import get_exchanges

templates = Jinja2Templates(directory="/app/exchange_radar/web/templates")


manager_trades = ConnectionTradesManager.get_instance()
manager_trades_dolphins = ConnectionTradesDolphinsManager.get_instance()
manager_trades_octopuses = ConnectionTradesOctopusesManager.get_instance()
manager_trades_whales = ConnectionTradesWhalesManager.get_instance()


class IndexBase(HTTPEndpoint):
    http_trades_url = settings.TRADES_HOST_URL
    http_stats_url = settings.TRADES_STATS_URL
    websocket_url = settings.TRADES_SOCKET_URL
    template_name = "index.html"

    def get(self, request):
        coin = request.path_params.get("coin", "BTC")
        context = {
            "request": request,
            "coin": coin,
            "http_trades_url": self.http_trades_url.format(coin=coin),
            "http_stats_url": self.http_stats_url.format(coin=coin),
            "websocket_url": self.websocket_url.format(coin=coin),
            "exchanges": get_exchanges(coin=coin),
            "max_rows": settings.DB_TABLE_MAX_ROWS,
        }
        return templates.TemplateResponse(self.template_name, context=context)


class IndexWhales(IndexBase):
    http_trades_url = settings.TRADES_WHALES_HOST_URL
    websocket_url = settings.TRADES_WHALES_SOCKET_URL
    template_name = "index-whales.html"


class IndexDolphins(IndexBase):
    http_trades_url = settings.TRADES_DOLPHINS_HOST_URL
    websocket_url = settings.TRADES_DOLPHINS_SOCKET_URL
    template_name = "index-dolphins.html"


class IndexOctopuses(IndexBase):
    http_trades_url = settings.TRADES_OCTOPUSES_HOST_URL
    websocket_url = settings.TRADES_OCTOPUSES_SOCKET_URL
    template_name = "index-octopuses.html"


class FeedBase(HTTPEndpoint):
    manager = manager_trades

    def __str__(self):
        return type(self).__name__

    async def post(self, request):
        coin = request.path_params["coin"]
        message = await request.json()
        await self.manager.broadcast(message, coin)
        # Db.write(cls_name=str(self), coin=coin, message=message)
        return JSONResponse({"r": True}, status_code=201)

    async def get(self, request):
        coin = request.path_params["coin"]
        rows = Db.read(cls_name=str(self), coin=coin)
        return JSONResponse({"r": rows}, status_code=200)


class FeedWhales(FeedBase):
    manager = manager_trades_whales


class FeedDolphins(FeedBase):
    manager = manager_trades_dolphins


class FeedOctopuses(FeedBase):
    manager = manager_trades_octopuses


class Stats(HTTPEndpoint):
    async def get(self, request):  # noqa
        trade_symbol = request.path_params["coin"]
        response = StatsSerializer(trade_symbol=trade_symbol)
        return JSONResponse(response.model_dump(), status_code=200)
