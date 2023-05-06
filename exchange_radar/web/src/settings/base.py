from environs import Env

env = Env()

DEBUG = env.bool("DEBUG")

DB_PATH = env.str("DB_PATH")

TRADES_SOCKET_URL = env.str("TRADES_SOCKET_URL")
TRADES_WHALES_SOCKET_URL = env.str("TRADES_WHALES_SOCKET_URL")
TRADES_DOLPHINS_SOCKET_URL = env.str("TRADES_DOLPHINS_SOCKET_URL")
TRADES_OCTOPUSES_SOCKET_URL = env.str("TRADES_OCTOPUSES_SOCKET_URL")

TRADES_HOST_URL = env.str("TRADES_HOST_URL")
TRADES_WHALES_HOST_URL = env.str("TRADES_WHALES_HOST_URL")
TRADES_DOLPHINS_HOST_URL = env.str("TRADES_DOLPHINS_HOST_URL")
TRADES_OCTOPUSES_HOST_URL = env.str("TRADES_OCTOPUSES_HOST_URL")

DB_TABLE_MAX_ROWS = env.int("DB_TABLE_MAX_ROWS")
