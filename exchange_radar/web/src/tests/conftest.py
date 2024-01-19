from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

with patch("redis.connection.ConnectionPool.get_connection"):
    from exchange_radar.web.src.main import app


@pytest.fixture
def client():
    with patch("exchange_radar.web.src.api.http.Feed.select_rows", return_value=[]):
        with TestClient(app) as client:
            yield client
