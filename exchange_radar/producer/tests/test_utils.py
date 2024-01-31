from unittest.mock import Mock

import pytest

from exchange_radar.producer.enums import Ranking
from exchange_radar.producer.utils import get_exchanges, get_ranking


@pytest.mark.parametrize(
    "currency, total, expected",
    [
        ("BTC", 0.666, Ranking.DOLPHIN),
        ("BTC", 0.01, None),
        ("BTC", 120.6, Ranking.WHALE),
        ("ETH", 5.99, Ranking.OCTOPUS),
        ("ETH", 0.599, None),
        ("ETH", 7.89, Ranking.DOLPHIN),
        ("USD", 145000.23, Ranking.WHALE),
        ("USDT", 999, None),
        ("USDT", 11050, Ranking.DOLPHIN),
        ("USD", 1050.40, Ranking.OCTOPUS),
    ],
)
def test_get_ranking(currency, total, expected):
    data = Mock()
    data.currency = currency
    data.total = total
    ranking = get_ranking(data=data)
    assert expected == ranking


def test_get_ranking__error():
    data = Mock()
    data.currency = "LTO"
    data.total = 123000
    with pytest.raises(ValueError) as exc_info:
        get_ranking(data=data)
    assert str(exc_info.value) == "Currency not configured LTO"


@pytest.mark.parametrize(
    "coin, expected",
    [
        ("BTC", "Binance, Coinbase, Kraken, Kucoin, OKX, Bybit, Bitstamp, MEXC, HTX"),
        ("ETH", "Binance, Coinbase, Kraken, Kucoin, OKX, Bybit, Bitstamp, MEXC, HTX"),
        ("LTO", "Binance, Kucoin"),
    ],
)
def test_get_exchanges(coin, expected):
    assert get_exchanges(coin=coin) == expected
