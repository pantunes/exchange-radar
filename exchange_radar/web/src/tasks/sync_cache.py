import logging

from exchange_radar.web.src.models import Feed, cache_pks
from exchange_radar.web.src.settings.base import BINANCE, COINBASE, KRAKEN, KUCOIN

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def sync_cache():
    logger.info("START sync_cache")

    cache_pks.clear()

    coins = list(set(BINANCE + COINBASE + KRAKEN + KUCOIN))

    for category in (
        "FeedBase",
        "FeedWhales",
        "FeedDolphins",
        "FeedOctopuses",
    ):
        for coin in coins:
            if not Feed.is_coin_selected(coin, category):
                logger.info(f"NOT SELECTED: Skipping {category} for {coin}")
                continue

            for obj in Feed.select_rows(coin=coin, category=category):
                cache_pks.__get__(coin=coin, category=category).append(obj["pk"])
            else:
                logger.info(f"EMPTY: Skipping {category} for {coin}")
                continue

    logger.info(cache_pks)

    logger.info("END sync_cache")
