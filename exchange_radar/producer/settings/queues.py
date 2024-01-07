from exchange_radar.producer.enums import Ranking
from exchange_radar.producer.settings import base as settings

QUEUES = {
    Ranking.WHALE: settings.RABBITMQ_TRADES_WHALES_QUEUE_NAME,
    Ranking.DOLPHIN: settings.RABBITMQ_TRADES_DOLPHIN_QUEUE_NAME,
    Ranking.OCTOPUS: settings.RABBITMQ_TRADES_OCTOPUS_QUEUE_NAME,
}
