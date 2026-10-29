from unittest.mock import AsyncMock, MagicMock, Mock, call

import pytest
from starlette.testclient import TestClient

from exchange_radar.feed import MAX_FEED_BATCH_SIZE
from exchange_radar.web.src import models
from exchange_radar.web.src.api import http


@pytest.mark.parametrize("category", [http.FeedBase, http.FeedWhales, http.FeedDolphins, http.FeedOctopuses])
def test_batch_preserves_every_message_order_coin_and_category(client, monkeypatch, category):
    broadcast = AsyncMock()
    save = Mock(return_value=[False, True, False])
    monkeypatch.setattr(category.manager, "broadcast", broadcast)
    monkeypatch.setattr(http.FeedModel, "save_batch", save)
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
    save.assert_called_once_with(
        category=category.__name__, trades=[(message["trade_symbol"], message) for message in messages]
    )


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
    monkeypatch.setattr(http.FeedModel, "save_batch", Mock(return_value=[False]))
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
    save_batch = Mock()
    monkeypatch.setattr(http.FeedBase.manager, "broadcast", broadcast)
    monkeypatch.setattr(http.FeedModel, "save_or_not", save)
    monkeypatch.setattr(http.FeedModel, "save_batch", save_batch)
    response = client.post(path, json=payload)
    assert response.status_code == 400
    broadcast.assert_not_awaited()
    save.assert_not_called()
    save_batch.assert_not_called()


def history_message(coin="BTC", index=0):
    return {
        "price": 2000.0 + index,
        "trade_time_ts": 1792933117 + index,
        "is_seller": bool(index % 2),
        "currency": "USDT",
        "trade_symbol": coin,
        "volume": 4.0 + index,
        "volume_trades": [1.5, 2.5],
        "number_trades": [1, 2],
        "message": f"trade {index}",
        "ranking": "Dolphin",
    }


@pytest.mark.parametrize("category", ["octopuses", "dolphins", "whales"])
@pytest.mark.parametrize("coins", [("BTC",), ("BTC", "ETH")])
def test_history_batch_persists_every_trade_once_and_trims_once_per_coin(client, monkeypatch, category, coins):
    database = MagicMock()
    monkeypatch.setattr(models, "redis", database)
    monkeypatch.setattr("redis_om.model.model.has_redis_json", lambda connection: True)
    trim = Mock()
    monkeypatch.setattr(http.FeedModel, "trim", trim)
    manager = getattr(http, f"Feed{category.capitalize()}").manager
    broadcast = AsyncMock()
    monkeypatch.setattr(manager, "broadcast", broadcast)
    messages = [history_message(coins[index % len(coins)], index) for index in range(50)]

    response = client.post(f"/api/feed/_batch/{category}", json=messages)

    assert response.status_code == 201
    assert response.json() == {"r": [True] * 50, "accepted": 50}
    assert broadcast.await_args_list == [call(message, message["trade_symbol"]) for message in messages]
    database.pipeline.assert_called_once_with(transaction=False)
    pipeline = database.pipeline.return_value.__enter__.return_value
    writes = pipeline.json.return_value.set.call_args_list
    assert len(writes) == 50
    assert len({write.args[0] for write in writes}) == 50
    assert [{key: write.args[2][key] for key in message} for write, message in zip(writes, messages)] == messages
    assert pipeline.expire.call_args_list == [call(write.args[0], models.FEED_EXPIRATION_SECONDS) for write in writes]
    pipeline.execute.assert_called_once()
    assert trim.call_args_list == [call(coin=coin, category=f"Feed{category.capitalize()}") for coin in coins]


def test_unsaved_category_accepts_whole_batch_without_history_database_work(client, monkeypatch):
    database = MagicMock()
    monkeypatch.setattr(models, "redis", database)
    monkeypatch.setattr(http.FeedBase.manager, "broadcast", AsyncMock())
    trim = Mock()
    monkeypatch.setattr(http.FeedModel, "trim", trim)

    response = client.post("/api/feed/_batch", json=[{"trade_symbol": coin} for coin in ["BTC", "ETH", "BTC"]])

    assert response.json() == {"r": [False, False, False], "accepted": 3}
    database.pipeline.assert_not_called()
    trim.assert_not_called()


def test_invalid_later_history_trade_does_not_partially_write_batch(client, monkeypatch):
    database = MagicMock()
    monkeypatch.setattr(models, "redis", database)
    monkeypatch.setattr("redis_om.model.model.has_redis_json", lambda connection: True)
    trim = Mock()
    monkeypatch.setattr(http.FeedModel, "trim", trim)
    valid, invalid = history_message(), history_message(index=1)
    invalid["ranking"] = "invalid ranking"

    with pytest.raises(ValueError):
        http.FeedModel.save_batch(category="FeedDolphins", trades=[("BTC", valid), ("BTC", invalid)])

    database.pipeline.assert_not_called()
    trim.assert_not_called()


@pytest.mark.parametrize("failure_stage", ["write", "trim"])
def test_history_database_failure_does_not_report_batch_success(client, monkeypatch, failure_stage):
    database = MagicMock()
    monkeypatch.setattr(models, "redis", database)
    monkeypatch.setattr("redis_om.model.model.has_redis_json", lambda connection: True)
    trim = Mock()
    monkeypatch.setattr(http.FeedModel, "trim", trim)
    monkeypatch.setattr(http.FeedDolphins.manager, "broadcast", AsyncMock())
    pipeline = database.pipeline.return_value.__enter__.return_value
    failure = ConnectionError("Redis unavailable")
    if failure_stage == "write":
        pipeline.execute.side_effect = failure
    else:
        trim.side_effect = failure

    with TestClient(client.app, raise_server_exceptions=False) as failing_client:
        response = failing_client.post("/api/feed/_batch/dolphins", json=[history_message()])

    assert response.status_code == 500

    if failure_stage == "write":
        trim.assert_not_called()
