import logging
from collections.abc import Callable
from time import sleep

import click
import pika
import requests
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import (
    AMQPConnectionError,
    ChannelWrongStateError,
    ConnectionClosedByBroker,
    StreamLostError,
)

from exchange_radar.consumer.delivery import Callback
from exchange_radar.consumer.settings import base as settings
from exchange_radar.feed import MAX_FEED_BATCH_SIZE

logger = logging.getLogger(__name__)

logging.getLogger("pika").propagate = False

ITER_SLEEP = 4.0


def setup_channel(channel: BlockingChannel, queue_name: str, callback: Callable):
    channel.basic_qos(prefetch_count=MAX_FEED_BATCH_SIZE)
    channel.basic_consume(queue=queue_name, on_message_callback=callback)


@click.command()
def main():  # pragma: no cover
    credentials = pika.PlainCredentials(settings.RABBITMQ_DEFAULT_USER, settings.RABBITMQ_DEFAULT_PASS)

    parameters = pika.ConnectionParameters(
        host=settings.RABBITMQ_HOST,
        port=settings.RABBITMQ_PORT,
        credentials=credentials,
        virtual_host=settings.RABBITMQ_DEFAULT_VHOST,
        heartbeat=settings.RABBITMQ_CONNECTION_HEARTBEAT,
        blocked_connection_timeout=settings.RABBITMQ_BLOCKED_CONNECTION_TIMEOUT,
    )

    while True:
        channel = None
        connection = None
        session = requests.Session()
        try:
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()

            for queue_name, url in (
                (settings.RABBITMQ_TRADES_QUEUE_NAME, settings.TRADES_HOST_URL),
                (
                    settings.RABBITMQ_TRADES_WHALES_QUEUE_NAME,
                    settings.TRADES_WHALES_HOST_URL,
                ),
                (
                    settings.RABBITMQ_TRADES_DOLPHIN_QUEUE_NAME,
                    settings.TRADES_DOLPHINS_HOST_URL,
                ),
                (
                    settings.RABBITMQ_TRADES_OCTOPUS_QUEUE_NAME,
                    settings.TRADES_OCTOPUSES_HOST_URL,
                ),
            ):
                setup_channel(
                    channel,
                    queue_name,
                    Callback(url=url, session=session).callback,
                )
            channel.start_consuming()
        except KeyboardInterrupt:
            if channel:
                channel.stop_consuming()
            logger.info("Quitting manually....")
            break
        except (
            StreamLostError,
            ConnectionClosedByBroker,
            ChannelWrongStateError,
        ) as error:
            logger.error(f"ERROR: {error}")
        except AMQPConnectionError:
            logger.error("ERROR: General AMQP Connection Error")
        except Exception as error:
            logger.error(f"GENERAL ERROR: {error}")
        finally:
            session.close()
            if connection is not None and connection.is_open:
                try:
                    connection.close()
                except pika.exceptions.AMQPError as error:
                    logger.warning("Error closing consumer connection: %s", error)
            sleep(ITER_SLEEP)
