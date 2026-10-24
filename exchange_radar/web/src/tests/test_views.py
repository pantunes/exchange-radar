import pytest
from starlette.websockets import WebSocketDisconnect


@pytest.mark.parametrize("coin", ["BTC", "ETH"])
def test_index(client, coin):
    response = client.get(f"/{coin}")
    assert response.status_code == 200
    assert "EQTY" not in response.text
    assert "Spot Equity" not in response.text
    assert "Spot Sonic" not in response.text
    assert 'href="/S"' not in response.text
    assert 'href="/history/S"' not in response.text
    assert 'href="/alerts/S"' not in response.text


@pytest.mark.parametrize("coin", ["xBTC", "ETxH"])
def test_index__invalid_coin(client, coin):
    response = client.get(f"/{coin}")
    assert response.status_code == 400
    assert "Invalid coin: " in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/{coin}",
        "/{coin}/octopuses",
        "/{coin}/dolphins",
        "/{coin}/whales",
        "/history/{coin}",
        "/alerts/{coin}",
        "/api/feed/{coin}",
        "/api/feed/{coin}/octopuses",
        "/api/feed/{coin}/dolphins",
        "/api/feed/{coin}/whales",
        "/api/stats/{coin}",
        "/api/history/{coin}",
        "/api/alerts/{coin}",
    ],
)
@pytest.mark.parametrize("coin", ["EQTY", "S"])
def test_retired_pair_is_not_available(client, path, coin):
    response = client.get(path.format(coin=coin))
    assert response.status_code == 400
    assert f"Invalid coin: {coin}" in response.text


@pytest.mark.parametrize("category", ["", "/octopuses", "/dolphins", "/whales"])
@pytest.mark.parametrize("coin", ["EQTY", "S"])
def test_retired_pair_cannot_open_a_trade_stream(client, category, coin):
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(f"/api/trades/{coin}{category}"):
            pytest.fail("The retired pair must not open a trade stream")
    assert error.value.code == 1008
