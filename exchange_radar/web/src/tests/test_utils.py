import pytest

from exchange_radar.web.src.utils import get_exchanges


@pytest.mark.parametrize(
    "coin, expected",
    [
        (
            "BTC",
            "<span id='binance' class='binance'>Binance</span> <span id='coinbase' class='coinbase'>Coinbase</span> "
            "<span id='kraken' class='kraken'>Kraken</span> <span id='kucoin' class='kucoin'>KuCoin</span> "
            "<span id='okx' class='okx'>OKX</span> <span id='bybit' class='bybit'>Bybit</span> "
            "<span id='bitstamp' class='bitstamp'>Bitstamp</span> <span id='mexc' class='mexc'>MEXC</span> "
            "<span id='htx' class='htx'>HTX</span>",
        ),
        (
            "ETH",
            "<span id='binance' class='binance'>Binance</span> <span id='coinbase' class='coinbase'>Coinbase</span> "
            "<span id='kraken' class='kraken'>Kraken</span> <span id='kucoin' class='kucoin'>KuCoin</span> "
            "<span id='okx' class='okx'>OKX</span> <span id='bybit' class='bybit'>Bybit</span> "
            "<span id='bitstamp' class='bitstamp'>Bitstamp</span> <span id='mexc' class='mexc'>MEXC</span> "
            "<span id='htx' class='htx'>HTX</span>",
        ),
        ("LTO", "<span id='binance' class='binance'>Binance</span> <span id='kucoin' class='kucoin'>KuCoin</span>"),
    ],
)
def test_get_exchanges(coin, expected):
    assert get_exchanges(coin=coin) == expected


def test_get_exchanges__error():
    with pytest.raises(ValueError) as exc_info:
        assert get_exchanges(coin="BLAH") == "anything"
    assert str(exc_info.value) == "No exchanges found for the coin BLAH"
