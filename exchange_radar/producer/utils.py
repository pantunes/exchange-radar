from decimal import Decimal

from exchange_radar.producer.enums import Ranking
from exchange_radar.producer.settings.exchanges import (
    BINANCE_COINS,
    BITSTAMP_COINS,
    BYBIT_COINS,
    COINBASE_COINS,
    HTX_COINS,
    KRAKEN_COINS,
    KUCOIN_COINS,
    MEXC_COINS,
    OKX_COINS,
)


def get_ranking(total: Decimal, currency: str) -> Ranking:
    if currency in (
        "USDT",
        "USD",
    ):
        if total > 100000.0:
            return Ranking.WHALE
        if total > 10000.0:
            return Ranking.DOLPHIN
        if total > 1000.0:
            return Ranking.OCTOPUS
        return Ranking.BREADCRUMBS

    if currency == "BTC":
        if total > 4.0:
            return Ranking.WHALE
        if total > 0.4:
            return Ranking.DOLPHIN
        if total > 0.04:
            return Ranking.OCTOPUS
        return Ranking.BREADCRUMBS

    if currency == "ETH":
        if total > 60.0:
            return Ranking.WHALE
        if total > 6.0:
            return Ranking.DOLPHIN
        if total > 0.6:
            return Ranking.OCTOPUS
        return Ranking.BREADCRUMBS

    raise ValueError(f"Currency not configured: {currency}")


def get_exchanges(coin: str) -> str:
    exchanges = [
        (BINANCE_COINS, "Binance"),
        (COINBASE_COINS, "Coinbase"),
        (KRAKEN_COINS, "Kraken"),
        (KUCOIN_COINS, "Kucoin"),
        (OKX_COINS, "OKX"),
        (BYBIT_COINS, "Bybit"),
        (BITSTAMP_COINS, "Bitstamp"),
        (MEXC_COINS, "MEXC"),
        (HTX_COINS, "HTX"),
    ]
    coin_length = len(coin)
    exchanges_selected = []

    for coins, exchange in exchanges:
        for _coin in coins:
            if _coin[:coin_length] == coin:
                exchanges_selected.append(exchange)
                break

    return ", ".join(exchanges_selected)
