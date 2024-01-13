import logging

from exchange_radar.producer.settings import base as settings

logging.basicConfig(
    format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
    level=logging.INFO if settings.DEBUG else logging.WARNING,
)
