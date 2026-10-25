from unittest.mock import AsyncMock, MagicMock, Mock, call

import pytest

from exchange_radar.feed import MAX_FEED_BATCH_SIZE
from exchange_radar.web.src import models
from exchange_radar.web.src.api import http


@pytest.mark.parametrize("category", [http.FeedBase, http.FeedWhales, http.FeedDolphins, http.FeedOctopuses])
def test_batch_preserves_every_message_order_coin_and_category(client, monkeypatch, category):
    broadcast = AsyncMock()
    save = Mock(side_effect=[False, True, False])
    monkeypatch.setattr(category.manager, "broadcast", broadcast)
    monkeypatch.setattr(http.FeedModel, "save_or_not", save)
    suffix = {
        http.FeedBase: "",
        http.FeedWhales: "/whales",
        http.FeedDolphins: "/dolphins",
        http.FeedOctopuses: "/octopuses",
    }[category]
    messages = [{"trade_symbol": coin, "id": index} for index, coin in enumerate(["BTC", "ETH", "BTC"])]
    response = client.post(f"/api/feed/_batch{suffix}", json=messages)
    assert response.status_code == 201
    assert response.json() == {"r": [False, True, False], "accepted": 3}
    assert broadcast.await_args_list == [call(message, message["trade_symbol"]) for message in messages]
    assert save.call_args_list == [
        call(coin=message["trade_symbol"], category=category.__name__, message=message) for message in messages
    ]


def test_single_trade_request_remains_compatible(client, monkeypatch):
    broadcast = AsyncMock()
    monkeypatch.setattr(http.FeedBase.manager, "broadcast", broadcast)
    monkeypatch.setattr(http.FeedModel, "save_or_not", Mock(return_value=False))
    message = {"trade_symbol": "BTC", "id": 1}
    response = client.post("/api/feed/BTC", json=message)
    assert response.status_code == 200
    assert response.json() == {"r": False}
    broadcast.assert_awaited_once_with(message, "BTC")


def test_batch_without_saved_trades_returns_success(client, monkeypatch):
    monkeypatch.setattr(http.FeedBase.manager, "broadcast", AsyncMock())
    monkeypatch.setattr(http.FeedModel, "save_or_not", Mock(return_value=False))
    response = client.post("/api/feed/BTC", json=[{"trade_symbol": "BTC"}])
    assert response.status_code == 200
    assert response.json() == {"r": [False], "accepted": 1}


@pytest.mark.parametrize("category", ["octopuses", "dolphins", "whales"])
@pytest.mark.parametrize("batch", [False, True])
@pytest.mark.parametrize(
    "volume_trades,number_trades",
    [(None, None), (None, [1, 2]), ([1.5, 2.5], None), ([1.5, 2.5], [1, 2])],
)
def test_feed_saves_trades_with_unavailable_statistics(
    client, monkeypatch, category, batch, volume_trades, number_trades
):
    database = MagicMock()
    monkeypatch.setattr(models, "redis", database)
    monkeypatch.setattr("redis_om.model.model.has_redis_json", lambda connection: True)
    trim = Mock()
    monkeypatch.setattr(http.FeedModel, "trim", trim)
    manager = getattr(http, f"Feed{category.capitalize()}").manager
    broadcast = AsyncMock()
    monkeypatch.setattr(manager, "broadcast", broadcast)
    message = {
        "price": 2000.0,
        "trade_time_ts": 1792933117,
        "is_seller": False,
        "currency": "USDT",
        "trade_symbol": "BTC",
        "volume": 4.0,
        "volume_trades": volume_trades,
        "number_trades": number_trades,
        "message": "Trade before both sides have daily statistics",
        "ranking": {"octopuses": "Octopus", "dolphins": "Dolphin", "whales": "Whale"}[category],
    }

    response = client.post(
        f"/api/feed/{'_batch' if batch else 'BTC'}/{category}", json=[message] if batch else message
    )

    assert response.status_code == 201
    assert response.json() == ({"r": [True], "accepted": 1} if batch else {"r": True})
    broadcast.assert_awaited_once_with(message, "BTC")
    database.pipeline.assert_called_once_with(transaction=False)
    pipeline = database.pipeline.return_value.__enter__.return_value
    saved_key, _, saved = pipeline.json.return_value.set.call_args.args
    assert saved["volume_trades"] == volume_trades
    assert saved["number_trades"] == number_trades
    pipeline.expire.assert_called_once_with(saved_key, models.FEED_EXPIRATION_SECONDS)
    pipeline.execute.assert_called_once()
    trim.assert_called_once_with(coin="BTC", category=f"Feed{category.capitalize()}")


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/api/feed/_batch", []),
        ("/api/feed/_batch", [{"trade_symbol": "BTC"}] * (MAX_FEED_BATCH_SIZE + 1)),
        ("/api/feed/_batch", [{"trade_symbol": "BTC"}, {}]),
        ("/api/feed/_batch", [{"trade_symbol": ""}]),
        ("/api/feed/_batch", [{"trade_symbol": 1}]),
        ("/api/feed/_batch", [1]),
        ("/api/feed/BTC", [{"trade_symbol": "ETH"}]),
        ("/api/feed/_batch", {"trade_symbol": "BTC"}),
        ("/api/feed/BTC", "invalid"),
    ],
)
def test_invalid_batch_is_rejected_before_any_trade_is_processed(client, monkeypatch, path, payload):
    broadcast = AsyncMock()
    save = Mock()
    monkeypatch.setattr(http.FeedBase.manager, "broadcast", broadcast)
    monkeypatch.setattr(http.FeedModel, "save_or_not", save)
    response = client.post(path, json=payload)
    assert response.status_code == 400
    broadcast.assert_not_awaited()
    save.assert_not_called()
