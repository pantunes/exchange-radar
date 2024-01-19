import pytest


@pytest.mark.parametrize("path", ["/feed/BTC", "/feed/BTC/whales", "/feed/BTC/dolphins", "/feed/BTC/octopuses"])
def test_feed_get(path, client):
    response = client.get(path)
    assert response.json() == {"r": []}
    assert response.status_code == 200


def test_feed_get__invalid_coin(client):
    response = client.get("/feed/BLAH")
    assert response.json() == {"detail": "Invalid coin: BLAH"}
    assert response.status_code == 400


@pytest.mark.parametrize("path", ["/fe/BTC", "/fseed/BTC/whsales", "/feed/BTC/dolpshins", "/feed/BTC/xoctopuses"])
def test_feed_get__url_does_not_exist(path, client):
    response = client.get("/BLAH/BTC")
    assert response.text == "Not Found"
    assert response.status_code == 404
