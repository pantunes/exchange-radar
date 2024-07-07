import logging

import click
from huey import RedisHuey
from huey.consumer import Consumer
from redis_om import get_redis_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


redis = get_redis_connection()
huey = RedisHuey("scheduler", host="redis")


# Register periodic Tasks
# noinspection PyUnresolvedReferences
from exchange_radar.scheduler.alerts.bullish import volume_buy_orders_against_volume_sell_orders  # noqa


@click.command()
def main():
    logger.info("Scheduler is starting...")
    consumer = Consumer(huey)
    consumer.run()
    logger.info("Scheduler has stopped...")
