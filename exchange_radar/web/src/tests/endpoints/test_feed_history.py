from unittest.mock import Mock

import pytest

from exchange_radar.web.src.api import http
from exchange_radar.web.src.settings import base as settings


@pytest.mark.parametrize("coin", ["BTC", "ETH", "LINK", "PEPE"])
@pytest.mark.parametrize("category", ["dolphins", "whales"])
def test_screen_sized_history_for_every_coin_and_category(client, monkeypatch, coin, category):
    select = Mock(return_value=[])
    monkeypatch.setattr(http.FeedModel, "select_rows", select)

    response = client.get(f"/api/feed/{coin}/{category}?limit=150")

    assert response.status_code == 200
    select.assert_called_once_with(coin=coin, category=f"Feed{category.capitalize()}", limit=150)
    assert http.FeedModel.is_coin_selected(coin, f"Feed{category.capitalize()}")


@pytest.mark.parametrize("category", ["FeedBase", "FeedOctopuses"])
def test_live_only_feeds_do_not_save_trades(category):
    # No message fields may be accessed or storage writes attempted.
    assert http.FeedModel.save_or_not("BTC", category, {}) is False


@pytest.mark.parametrize("coin", ["BTC", "ETH", "LINK", "PEPE"])
@pytest.mark.parametrize("category", ["octopuses", "dolphins", "whales"])
def test_only_saved_feeds_enable_screen_sized_history(client, coin, category):
    response = client.get(f"/{coin}/{category}")
    enabled = "false" if category == "octopuses" else "true"
    assert f"const saved_history = {enabled};" in response.text


@pytest.mark.parametrize("limit", ["0", "-1", "1.5", "invalid", ""])
def test_invalid_history_limit_is_rejected(client, monkeypatch, limit):
    select = Mock()
    monkeypatch.setattr(http.FeedModel, "select_rows", select)
    response = client.get(f"/api/feed/BTC/whales?limit={limit}")
    assert response.status_code == 400
    select.assert_not_called()


@pytest.mark.parametrize("limit", [None, "999999999"])
def test_history_request_has_a_bounded_default_and_maximum(client, monkeypatch, limit):
    select = Mock(return_value=[])
    monkeypatch.setattr(http.FeedModel, "select_rows", select)
    query = "" if limit is None else f"?limit={limit}"
    response = client.get(f"/api/feed/BTC/whales{query}")
    assert response.status_code == 200
    expected = settings.REDIS_MAX_ROWS if limit is None else settings.FEED_RETENTION_ROWS
    select.assert_called_once_with(coin="BTC", category="FeedWhales", limit=expected)
