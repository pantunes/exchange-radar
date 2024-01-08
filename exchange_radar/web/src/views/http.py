from datetime import datetime

import redis
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
from exchange_radar.web.src.utils import get_exchanges

templates = Jinja2Templates(directory="/app/exchange_radar/web/templates")

redis = redis.StrictRedis(
    host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB
)

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
        Db.write(cls_name=str(self), coin=coin, message=message)
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
        today_date = datetime.today().date().strftime("%Y-%m-%d")

        coin = request.path_params["coin"]

        response = {
            "trade_symbol": coin,
            "volume": None,
            "volume_trades": [],
            "number_trades": [],
        }

        volume = float(redis.hget(today_date, f"{coin}_VOLUME"))
        vol_trades_buy_orders = float(
            redis.hget(today_date, f"{coin}_VOLUME_TRADES_BUY_ORDERS")
        )
        vol_trades_sell_orders = float(
            redis.hget(today_date, f"{coin}_VOLUME_TRADES_SELL_ORDERS")
        )
        num_trades_buy_orders = int(
            redis.hget(today_date, f"{coin}_NUMBER_TRADES_BUY_ORDERS")
        )
        num_trades_sell_orders = int(
            redis.hget(today_date, f"{coin}_NUMBER_TRADES_SELL_ORDERS")
        )

        response["volume"] = volume
        response["volume_trades"] = [vol_trades_buy_orders, vol_trades_sell_orders]
        response["number_trades"] = [num_trades_buy_orders, num_trades_sell_orders]

        return JSONResponse(response, status_code=200)
