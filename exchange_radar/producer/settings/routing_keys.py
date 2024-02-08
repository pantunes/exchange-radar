from exchange_radar.producer.enums import Ranking
from exchange_radar.producer.settings import base as settings

ROUTING_KEYS = {
    Ranking.WHALE: settings.RABBITMQ_TRADES_WHALES_ROUTING_KEY,
    Ranking.DOLPHIN: settings.RABBITMQ_TRADES_DOLPHIN_ROUTING_KEY,
    Ranking.OCTOPUS: settings.RABBITMQ_TRADES_OCTOPUS_ROUTING_KEY,
}
