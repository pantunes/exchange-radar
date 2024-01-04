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

TRADES_HOST_URL = env.str("TRADES_HOST_URL")
TRADES_WHALES_HOST_URL = env.str("TRADES_WHALES_HOST_URL")
TRADES_DOLPHINS_HOST_URL = env.str("TRADES_DOLPHINS_HOST_URL")
TRADES_OCTOPUSES_HOST_URL = env.str("TRADES_OCTOPUSES_HOST_URL")

# Regarding TCP/IP Protocol packet retransmission window,
# on connect() add a bit more than a multiple of 3.
# In seconds
POST_CONNECT_TIMEOUT = 3.05
POST_READ_TIMEOUT = 3.0
