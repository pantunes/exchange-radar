from environs import Env

env = Env()


EXCHANGES: dict[str:str] = {
    "binance": "BinanceTradesTask",
    "bybit": "BybitTradesTask",
    "kucoin": "KuCoinTradesTask",
    "coinbase": "CoinbaseTradesTask",
    "kraken": "KrakenTradesTask",
    "okx": "OkxTradesTask",
    "bitstamp": "BitstampTradesTask",
    "mexc": "MexcTradesTask",
    "htx": "HtxTradesTask",
}

EXCHANGES_LIST = list(EXCHANGES.keys())

BINANCE_COINS = env.list("BINANCE_COINS", delimiter=" ")
BYBIT_COINS = env.list("BYBIT_COINS", delimiter=" ")
KUCOIN_COINS = env.list("KUCOIN_COINS", delimiter=" ")
COINBASE_COINS = env.list("COINBASE_COINS", delimiter=" ")
KRAKEN_COINS = env.list("KRAKEN_COINS", delimiter=" ")
OKX_COINS = env.list("OKX_COINS", delimiter=" ")
BITSTAMP_COINS = env.list("BITSTAMP_COINS", delimiter=" ")
MEXC_COINS = env.list("MEXC_COINS", delimiter=" ")
HTX_COINS = env.list("HTX_COINS", delimiter=" ")
