from starlette.endpoints import HTTPEndpoint
from starlette.responses import JSONResponse

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
from exchange_radar.web.src.serializers.http import ParamsInputSerializer

manager_trades = ConnectionTradesManager.get_instance()
manager_trades_dolphins = ConnectionTradesDolphinsManager.get_instance()
manager_trades_octopuses = ConnectionTradesOctopusesManager.get_instance()
manager_trades_whales = ConnectionTradesWhalesManager.get_instance()


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
    async def get(_, data: ParamsInputSerializer):
        data = HistoryModel(trade_symbol=data.coin)
        return JSONResponse(data.model_dump(), status_code=200)


REST_ENDPOINTS = (
    FeedBase,
    FeedWhales,
    FeedDolphins,
    FeedOctopuses,
    Stats,
    History,
)
