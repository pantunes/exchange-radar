from exchange_radar.web.src.settings import base as settings


def get_exchanges(coin: str) -> str:
    txt = []

    if coin in settings.BINANCE:
        txt.append("<span class='binance'>Binance</span>")
    if coin in settings.COINBASE:
        txt.append("<span class='coinbase'>Coinbase</span>")
    if coin in settings.KRAKEN:
        txt.append("<span class='kraken'>Kraken</span>")
    if coin in settings.KUCOIN:
        txt.append("<span class='kucoin'>Kucoin</span>")

    return ", ".join(txt)
