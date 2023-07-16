from exchange_radar.web.src.settings import base as settings


def get_exchanges(coin: str) -> str:
    txt = []

    if coin in settings.BINANCE:
        txt.append("Binance")
    if coin in settings.KUCOIN:
        txt.append("Kucoin")
    if coin in settings.COINBASE:
        txt.append("Coinbase")

    return ", ".join(txt)
