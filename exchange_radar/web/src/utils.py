from exchange_radar.web.src.settings import base as settings


def get_exchanges(coin: str) -> str:
    exchanges: list[str] = []

    if coin in settings.BINANCE:
        exchanges.append("<span class='binance'>Binance</span>")
    if coin in settings.COINBASE:
        exchanges.append("<span class='coinbase'>Coinbase</span>")
    if coin in settings.KRAKEN:
        exchanges.append("<span class='kraken'>Kraken</span>")
    if coin in settings.KUCOIN:
        exchanges.append("<span class='kucoin'>KuCoin</span>")
    if coin in settings.OKX:
        exchanges.append("<span class='okx'>OKX</span>")
    if coin in settings.BYBIT:
        exchanges.append("<span class='bybit'>Bybit</span>")
    if coin in settings.BITSTAMP:
        exchanges.append("<span class='bitstamp'>Bitstamp</span>")
    if coin in settings.MEXC:
        exchanges.append("<span class='mexc'>MEXC</span>")
    if coin in settings.HTX:
        exchanges.append("<span class='htx'>HTX</span>")

    if len(exchanges) == 0:
        raise ValueError(f"No exchanges found for the coin {coin}")

    return " ".join(exchanges)
