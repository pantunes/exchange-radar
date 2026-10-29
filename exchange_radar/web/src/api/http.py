from starlette.endpoints import HTTPEndpoint
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from exchange_radar.feed import MAX_FEED_BATCH_SIZE
from exchange_radar.web.src.manager import (
    ConnectionTradesDolphinsManager,
    ConnectionTradesManager,
    ConnectionTradesOctopusesManager,
    ConnectionTradesWhalesManager,
)
from exchange_radar.web.src.models import Alerts as AlertsModel
from exchange_radar.web.src.models import Feed as FeedModel
from exchange_radar.web.src.models import History as HistoryModel
from exchange_radar.web.src.models import Stats as StatsModel
from exchange_radar.web.src.models import Status as StatusModel
from exchange_radar.web.src.serializers.decorators import validate
from exchange_radar.web.src.serializers.http import ParamsInputSerializer
from exchange_radar.web.src.settings import base as settings

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
        payload = await request.json()
        if isinstance(payload, list):
            if not 1 <= len(payload) <= MAX_FEED_BATCH_SIZE or any(
                not isinstance(message, dict)
                or not isinstance(message.get("trade_symbol"), str)
                or not message["trade_symbol"]
                or (coin != "_batch" and message["trade_symbol"] != coin)
                for message in payload
            ):
                raise HTTPException(400, "Invalid trade batch")
            for message in payload:
                symbol = message["trade_symbol"]
                await self.manager.broadcast(message, symbol)
            saved = FeedModel.save_batch(
                category=str(self), trades=[(message["trade_symbol"], message) for message in payload]
            )
            return JSONResponse({"r": saved, "accepted": len(saved)}, status_code=201 if any(saved) else 200)
        if coin == "_batch" or not isinstance(payload, dict):
            raise HTTPException(400, "Expected a trade batch")
        await self.manager.broadcast(payload, coin)
        is_saved = FeedModel.save_or_not(coin=coin, category=str(self), message=payload)
        return JSONResponse({"r": is_saved}, status_code=201 if is_saved else 200)

    @validate(serializer=ParamsInputSerializer)
    async def get(self, request, data: ParamsInputSerializer):
        """
        tags:
            - feed
        summary: List of matched market orders.
        parameters:
            - name: coin
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: List of matched market orders.
            400:
                description: Error in input validation.
        """

        try:
            limit = int(request.query_params.get("limit", settings.REDIS_MAX_ROWS))
        except ValueError:
            raise HTTPException(400, "limit must be a positive integer")
        if limit < 1:
            raise HTTPException(400, "limit must be a positive integer")
        rows = FeedModel.select_rows(
            coin=data.coin, category=str(self), limit=min(limit, settings.FEED_RETENTION_ROWS)
        )
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
        """
        tags:
            - stats
        summary: Daily matched market orders metrics.
        parameters:
            - name: coin
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: Daily matched market orders metrics.
            400:
                description: Error in input validation.
        """

        data = StatsModel(trade_symbol=data.coin)
        return JSONResponse(data.model_dump(), status_code=200)


class History(HTTPEndpoint):
    @staticmethod
    @validate(serializer=ParamsInputSerializer)
    async def get(_, data: ParamsInputSerializer):
        """
        tags:
            - history
        summary: Daily matched market orders history data.
        parameters:
            - name: coin
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: Daily matched market orders history data.
            400:
                description: Error in input validation.
        """

        data = HistoryModel(trade_symbol=data.coin)
        return JSONResponse(data.model_dump(), status_code=200)


class Alerts(HTTPEndpoint):
    @staticmethod
    @validate(serializer=ParamsInputSerializer)
    async def get(_, data: ParamsInputSerializer):
        """
        tags:
            - alerts
        summary: Price change alerts checked every 1 or 10 minutes.
        parameters:
            - name: coin
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: List of alerts.
            400:
                description: Error in input validation.
        """
        data = AlertsModel.rows(trade_symbol=data.coin)
        return JSONResponse(data, status_code=200)


class Status(HTTPEndpoint):
    @staticmethod
    async def get(_):
        """
        tags:
            - status
        summary: Exchanges connection status.
        responses:
            200:
                description: Exchanges connection status.
        """

        data = StatusModel()
        return JSONResponse(data.model_dump(), status_code=200)


REST_ENDPOINTS = (
    Alerts,
    FeedBase,
    FeedWhales,
    FeedDolphins,
    FeedOctopuses,
    Stats,
    History,
    Status,
)
