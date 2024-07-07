from environs import Env

env = Env()

DEBUG = env.bool("DEBUG")

BINANCE = env.list("BINANCE")
BYBIT = env.list("BYBIT")
COINBASE = env.list("COINBASE")
KRAKEN = env.list("KRAKEN")
KUCOIN = env.list("KUCOIN")
OKX = env.list("OKX")
BITSTAMP = env.list("BITSTAMP")
MEXC = env.list("MEXC")
HTX = env.list("HTX")

COINS = list(set(BINANCE + COINBASE + KRAKEN + KUCOIN + OKX + BITSTAMP + MEXC + HTX))
