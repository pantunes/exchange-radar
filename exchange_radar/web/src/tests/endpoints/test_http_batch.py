from unittest.mock import AsyncMock, Mock, call

import pytest

from exchange_radar.feed import MAX_FEED_BATCH_SIZE
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
