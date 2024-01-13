import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def sync_cache():
    logger.info("sync_cache")
