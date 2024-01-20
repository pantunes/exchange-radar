import pytest

from exchange_radar.web.src.utils import get_exchanges


@pytest.mark.parametrize(
    "coin, expected",
    [
        (
            "BTC",
            "<span class='binance'>Binance</span> <span class='coinbase'>Coinbase</span> "
            "<span class='kraken'>Kraken</span> <span class='kucoin'>KuCoin</span> "
            "<span class='okx'>OKX</span>",
        ),
        (
            "ETH",
            "<span class='binance'>Binance</span> <span class='coinbase'>Coinbase</span> "
            "<span class='kraken'>Kraken</span> <span class='kucoin'>KuCoin</span> "
            "<span class='okx'>OKX</span>",
        ),
        ("LTO", "<span class='binance'>Binance</span> <span class='kucoin'>KuCoin</span>"),
    ],
)
def test_get_exchanges(coin, expected):
    assert get_exchanges(coin=coin) == expected


def test_get_exchanges__error():
    with pytest.raises(ValueError) as exc_info:
        assert get_exchanges(coin="BLAH") == "anything"
    assert str(exc_info.value) == "No exchanges found for the coin BLAH"
