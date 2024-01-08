from environs import Env

env = Env()

DEBUG = env.bool("DEBUG")

REDIS_HOST = env.str("REDIS_HOST", default=None)
REDIS_PORT = env.int("REDIS_PORT", default=None)
REDIS_DB = env.int("REDIS_DB", default=None)

DB_PATH = env.str("DB_PATH")
DB_TABLE_MAX_ROWS = env.int("DB_TABLE_MAX_ROWS")

TRADES_SOCKET_URL = env.str("TRADES_SOCKET_URL")
TRADES_WHALES_SOCKET_URL = env.str("TRADES_WHALES_SOCKET_URL")
TRADES_DOLPHINS_SOCKET_URL = env.str("TRADES_DOLPHINS_SOCKET_URL")
TRADES_OCTOPUSES_SOCKET_URL = env.str("TRADES_OCTOPUSES_SOCKET_URL")

TRADES_HOST_URL = env.str("TRADES_HOST_URL")
TRADES_WHALES_HOST_URL = env.str("TRADES_WHALES_HOST_URL")
TRADES_DOLPHINS_HOST_URL = env.str("TRADES_DOLPHINS_HOST_URL")
TRADES_OCTOPUSES_HOST_URL = env.str("TRADES_OCTOPUSES_HOST_URL")

TRADES_STATS_URL = env.str("TRADES_STATS_URL")

BINANCE = env.list("BINANCE")
COINBASE = env.list("COINBASE")
KRAKEN = env.list("KRAKEN")
KUCOIN = env.list("KUCOIN")
