import pytest


@pytest.mark.parametrize("coin", ["BTC", "ETH"])
def test_index(client, coin):
    response = client.get(coin)
    assert response.status_code == 200
