import logging

from exchange_radar.web.src.models import FEED_EXPIRATION_SECONDS, Feed, redis

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def expire_feed_rows():
    """Give an expiry to feed rows saved before they had one (e.g. retired coins)."""
    logger.info("START expire_feed_rows")

    count = 0
    for pk in Feed.all_pks():
        count += redis.expire(Feed.make_primary_key(pk), FEED_EXPIRATION_SECONDS, nx=True)

    logger.info(f"END expire_feed_rows: {count} rows updated")
