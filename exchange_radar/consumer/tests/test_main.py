import logging
from unittest.mock import patch

from requests.exceptions import HTTPError

from exchange_radar.consumer.main import Callback


@patch("exchange_radar.consumer.main.requests.post")
def tests_callback(mock_post, caplog, channel, method, properties):
    body = b'{"trade_symbol": "BTCUSDT"}'
    caplog.set_level(logging.INFO)
    Callback(url="https://").callback(channel, method, properties, body)
    assert "CONSUMER - start" in caplog.text
    assert "CONSUMER - data: {'trade_symbol': 'BTCUSDT'}" in caplog.text
    assert "CONSUMER - end" in caplog.text


@patch("exchange_radar.consumer.main.requests.post", side_effect=HTTPError("Blah"))
def tests_callback__error(mock_post, caplog, channel, method, properties):
    body = b'{"trade_symbol": "BTCUSDT"}'
    Callback(url="https://").callback(channel, method, properties, body)
    assert "POST https:// Error: Blah" in caplog.text
