from environs import Env

env = Env()


EXCHANGES: dict[str:str] = {
    "binance": "BinanceTradesTask",
    "kucoin": "KuCoinTradesTask",
    "coinbase": "CoinbaseTradesTask",
    "kraken": "KrakenTradesTask",
    "okx": "OkxTradesTask",
}

EXCHANGES_LIST = list(EXCHANGES.keys())

BINANCE_COINS = env.list("BINANCE_COINS", delimiter=" ")
KUCOIN_COINS = env.list("KUCOIN_COINS", delimiter=" ")
COINBASE_COINS = env.list("COINBASE_COINS", delimiter=" ")
KRAKEN_COINS = env.list("KRAKEN_COINS", delimiter=" ")
OKX_COINS = env.list("OKX_COINS", delimiter=" ")
