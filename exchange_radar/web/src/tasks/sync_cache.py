import logging

from exchange_radar.web.src.cache import feed_cached_pks
from exchange_radar.web.src.models import Feed
from exchange_radar.web.src.settings.base import COINS

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def sync_feed_cache():
    logger.info("START sync_feed_cache")

    feed_cached_pks.clear()

    for category in (
        "FeedBase",
        "FeedWhales",
        "FeedDolphins",
        "FeedOctopuses",
    ):
        for coin in COINS:
            if not Feed.is_coin_selected(coin, category):
                logger.info(f"NOT SELECTED: Skipping {category} for {coin}")
                continue

            for obj in Feed.select_rows(coin=coin, category=category):
                feed_cached_pks.__get__(coin=coin, category=category).append(obj["pk"])
            else:
                logger.info(f"EMPTY: Skipping {category} for {coin}")
                continue

    logger.info(feed_cached_pks)

    logger.info("END sync_feed_cache")
