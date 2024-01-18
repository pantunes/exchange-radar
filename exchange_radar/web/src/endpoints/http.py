from starlette.endpoints import HTTPEndpoint
from starlette.responses import JSONResponse
from starlette.templating import Jinja2Templates

from exchange_radar.web.src.manager import (
    ConnectionTradesDolphinsManager,
    ConnectionTradesManager,
    ConnectionTradesOctopusesManager,
    ConnectionTradesWhalesManager,
)
from exchange_radar.web.src.models import Feed
from exchange_radar.web.src.models import History as HistoryModel
from exchange_radar.web.src.models import Stats as StatsModel
from exchange_radar.web.src.serializers.decorators import validate
from exchange_radar.web.src.serializers.http import (
    IndexParamsInputSerializer,
    ParamsInputSerializer,
)
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
    template_name = "index.j2"

    @validate(serializer=IndexParamsInputSerializer)
    async def get(self, request, data: ParamsInputSerializer):
        context = {
            "request": request,
            "coin": data.coin,
            "http_trades_url": self.http_trades_url.format(coin=data.coin),
            "http_stats_url": self.http_stats_url.format(coin=data.coin),
            "websocket_url": self.websocket_url.format(coin=data.coin),
            "exchanges": get_exchanges(coin=data.coin),
            "max_rows": settings.REDIS_MAX_ROWS,
        }
        return templates.TemplateResponse(self.template_name, context=context)


class IndexWhales(IndexBase):
    http_trades_url = settings.TRADES_WHALES_HOST_URL
    websocket_url = settings.TRADES_WHALES_SOCKET_URL
    template_name = "index-whales.j2"


class IndexDolphins(IndexBase):
    http_trades_url = settings.TRADES_DOLPHINS_HOST_URL
    websocket_url = settings.TRADES_DOLPHINS_SOCKET_URL
    template_name = "index-dolphins.j2"


class IndexOctopuses(IndexBase):
    http_trades_url = settings.TRADES_OCTOPUSES_HOST_URL
    websocket_url = settings.TRADES_OCTOPUSES_SOCKET_URL
    template_name = "index-octopuses.j2"


class FeedBase(HTTPEndpoint):
    manager = manager_trades

    def __str__(self):
        return type(self).__name__

    async def post(self, request):
        """internal endpoint"""
        coin = request.path_params["coin"]
        message = await request.json()
        await self.manager.broadcast(message, coin)
        is_saved = Feed.save_or_not(coin=coin, category=str(self), message=message)
        return JSONResponse({"r": is_saved}, status_code=201 if is_saved else 200)

    @validate(serializer=ParamsInputSerializer)
    async def get(self, _, data: ParamsInputSerializer):
        rows = Feed.select_rows(coin=data.coin, category=str(self))
        return JSONResponse({"r": rows}, status_code=200)


class FeedWhales(FeedBase):
    manager = manager_trades_whales


class FeedDolphins(FeedBase):
    manager = manager_trades_dolphins


class FeedOctopuses(FeedBase):
    manager = manager_trades_octopuses


class Stats(HTTPEndpoint):
    @staticmethod
    @validate(serializer=ParamsInputSerializer)
    async def get(_, data: ParamsInputSerializer):
        data = StatsModel(trade_symbol=data.coin)
        return JSONResponse(data.model_dump(), status_code=200)


class History(HTTPEndpoint):
    @staticmethod
    @validate(serializer=ParamsInputSerializer)
    async def get(request, data: ParamsInputSerializer):
        data = HistoryModel(trade_symbol=data.coin)
        context = {
            "request": request,
            "rows": data.model_dump()["rows"],
            "num_months": int(settings.REDIS_EXPIRATION / 30),
        }
        return templates.TemplateResponse("history.j2", context=context)


async def exc_handler(request, exc):
    context = {"request": request, "error_message": exc.detail}
    return templates.TemplateResponse("error.j2", context=context, status_code=exc.status_code)
