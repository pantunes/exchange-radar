from decimal import Decimal
from unittest.mock import Mock

import pytest

from exchange_radar.producer.enums import Ranking
from exchange_radar.producer.utils import get_exchanges, get_ranking


@pytest.mark.parametrize(
    "currency, total, expected",
    [
        ("BTC", Decimal("0.666"), Ranking.DOLPHIN),
        ("BTC", Decimal("0.01"), Ranking.BREADCRUMBS),
        ("BTC", Decimal("120.6"), Ranking.WHALE),
        ("ETH", Decimal("5.99"), Ranking.OCTOPUS),
        ("ETH", Decimal("0.599"), Ranking.BREADCRUMBS),
        ("ETH", Decimal("7.89"), Ranking.DOLPHIN),
        ("USD", Decimal("145000.23"), Ranking.WHALE),
        ("USDT", Decimal("999"), Ranking.BREADCRUMBS),
        ("USDT", Decimal("11050"), Ranking.DOLPHIN),
        ("USD", Decimal("1050.40"), Ranking.OCTOPUS),
    ],
)
def test_get_ranking(currency, total, expected):
    data = Mock()
    data.currency = currency
    data.total = total
    ranking = get_ranking(total=data.total, currency=data.currency)
    assert expected == ranking


def test_get_ranking__error():
    data = Mock()
    data.currency = "LTO"
    data.total = Decimal("123000")
    with pytest.raises(ValueError) as exc_info:
        get_ranking(total=data.total, currency=data.currency)
    assert str(exc_info.value) == "Currency not configured: LTO"


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
