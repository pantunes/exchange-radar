import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def sync_cache():
    logger.info("sync_cache")
