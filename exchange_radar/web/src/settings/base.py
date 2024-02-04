from environs import Env

env = Env()

DEBUG = env.bool("DEBUG")

REDIS_HOST = env.str("REDIS_HOST", default=None)
REDIS_PORT = env.int("REDIS_PORT", default=None)
REDIS_DB = env.int("REDIS_DB", default=None)

REDIS_MAX_ROWS = env.int("REDIS_MAX_ROWS")
REDIS_EXPIRATION = env.int("REDIS_EXPIRATION")  # in days

TRADES_SOCKET_URL = env.str("TRADES_SOCKET_URL")
TRADES_WHALES_SOCKET_URL = env.str("TRADES_WHALES_SOCKET_URL")
TRADES_DOLPHINS_SOCKET_URL = env.str("TRADES_DOLPHINS_SOCKET_URL")
TRADES_OCTOPUSES_SOCKET_URL = env.str("TRADES_OCTOPUSES_SOCKET_URL")

TRADES_HOST_URL = env.str("TRADES_HOST_URL")
TRADES_WHALES_HOST_URL = env.str("TRADES_WHALES_HOST_URL")
TRADES_DOLPHINS_HOST_URL = env.str("TRADES_DOLPHINS_HOST_URL")
TRADES_OCTOPUSES_HOST_URL = env.str("TRADES_OCTOPUSES_HOST_URL")

TRADES_STATS_URL = env.str("TRADES_STATS_URL")
TRADES_HISTORY_URL = env.str("TRADES_HISTORY_URL")

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

EXCHANGES = (
    "binance",
    "coinbase",
    "kraken",
    "kucoin",
    "okx",
    "bybit",
    "bitstamp",
    "mexc",
    "htx",
)

EXCHANGES_STATUS_TTL = 30.0  # in seconds
