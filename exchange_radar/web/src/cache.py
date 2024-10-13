import logging

from exchange_radar.web.src.settings import base as settings
from exchange_radar.web.src.types import ERdefaultdict

logger = logging.getLogger(__name__)


feed_cached_pks = ERdefaultdict(list)


class FeedCache:
    @staticmethod
    def delete_and_get_pk(obj, *, coin: str, category: str) -> str | None:
        feed_cached_pks.__get__(coin=coin, category=category).append(obj.pk)
        logger.info(f"CACHED_FEED_PKS: {feed_cached_pks}")

        count = len(feed_cached_pks.__get__(coin=coin, category=category))
        logger.info(f"COUNT: {count}")

        if count <= settings.REDIS_MAX_ROWS:
            return None

        obj2del_pk = feed_cached_pks.__get__(coin=coin, category=category).pop(0)
        return obj2del_pk
