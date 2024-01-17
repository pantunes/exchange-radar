from environs import Env

env = Env()

DEBUG = env.bool("DEBUG")

RABBITMQ_EXCHANGE = env.str("RABBITMQ_EXCHANGE")
RABBITMQ_HOST = env.str("RABBITMQ_HOST")
RABBITMQ_PORT = env.int("RABBITMQ_PORT")
RABBITMQ_TRADES_QUEUE_NAME = env.str("RABBITMQ_TRADES_QUEUE_NAME")
RABBITMQ_TRADES_WHALES_QUEUE_NAME = env.str("RABBITMQ_TRADES_WHALES_QUEUE_NAME")
RABBITMQ_TRADES_DOLPHIN_QUEUE_NAME = env.str("RABBITMQ_TRADES_DOLPHIN_QUEUE_NAME")
RABBITMQ_TRADES_OCTOPUS_QUEUE_NAME = env.str("RABBITMQ_TRADES_OCTOPUS_QUEUE_NAME")

RABBITMQ_DEFAULT_USER = env.str("RABBITMQ_DEFAULT_USER")
RABBITMQ_DEFAULT_PASS = env.str("RABBITMQ_DEFAULT_PASS")
RABBITMQ_DEFAULT_VHOST = env.str("RABBITMQ_DEFAULT_VHOST")

RABBITMQ_CONNECTION_HEARTBEAT = env.int("RABBITMQ_CONNECTION_HEARTBEAT")
RABBITMQ_BLOCKED_CONNECTION_TIMEOUT = env.int("RABBITMQ_BLOCKED_CONNECTION_TIMEOUT")

REDIS_HOST = env.str("REDIS_HOST", default=None)
REDIS_PORT = env.int("REDIS_PORT", default=None)
REDIS_DB = env.int("REDIS_DB", default=None)

REDIS_EXPIRATION = env.int("REDIS_EXPIRATION")  # in days

CURRENCIES = ["USDT", "BTC", "ETH", "USD"]
