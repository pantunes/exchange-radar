import pytest


@pytest.mark.parametrize("coin", ["BTC", "ETH"])
def test_index(client, coin):
    response = client.get(f"/{coin}")
    assert response.status_code == 200


@pytest.mark.parametrize("coin", ["xBTC", "ETxH"])
def test_index__invalid_coin(client, coin):
    response = client.get(f"/{coin}")
    assert response.status_code == 400
    assert "Invalid coin: " in response.text
