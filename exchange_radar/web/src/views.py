from starlette.endpoints import HTTPEndpoint
from starlette.templating import Jinja2Templates

from exchange_radar import __version__
from exchange_radar.web.src.manager import (
    ConnectionTradesDolphinsManager,
    ConnectionTradesManager,
    ConnectionTradesOctopusesManager,
    ConnectionTradesWhalesManager,
)
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
            "coin": data.coin,
            "http_trades_url": self.http_trades_url.format(coin=data.coin),
            "http_stats_url": self.http_stats_url.format(coin=data.coin),
            "websocket_url": self.websocket_url.format(coin=data.coin),
            "exchanges": get_exchanges(coin=data.coin),
            "max_rows": settings.REDIS_MAX_ROWS,
            "version": __version__,
        }
        return templates.TemplateResponse(request, self.template_name, context=context)


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


class History(HTTPEndpoint):
    @staticmethod
    @validate(serializer=ParamsInputSerializer)
    async def get(request, data: ParamsInputSerializer):
        context = {
            "coin": data.coin,
            "http_history_url": settings.TRADES_HISTORY_URL.format(coin=data.coin),
            "num_months": int(settings.REDIS_EXPIRATION / 30),
            "version": __version__,
        }
        return templates.TemplateResponse(request, "history.j2", context=context)
