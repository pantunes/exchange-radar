import json
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
from pika.spec import Basic

from exchange_radar.consumer.settings import base as settings

logger = logging.getLogger(__name__)

logging.getLogger("pika").propagate = False


ITER_SLEEP = 4.0


class Callback:
    def __init__(self, url: str):
        self.url = url

    def callback(
        self,
        channel: BlockingChannel,
        method: Basic.Deliver,
        properties: pika.BasicProperties,
        body: bytes,
    ):
        logger.info("CONSUMER - start")

        data = json.loads(body)

        logger.info(f"CONSUMER - data: {data}")

        url = self.url.format(coin=data["trade_symbol"])
        try:
            response = requests.post(
                url=url,
                json=data,
                timeout=(settings.POST_CONNECT_TIMEOUT, settings.POST_READ_TIMEOUT),
            )
            response.raise_for_status()
        except (
            requests.exceptions.HTTPError,  # 4xx, 5xx errors
            requests.exceptions.Timeout,
            requests.exceptions.TooManyRedirects,
            requests.exceptions.RequestException,
        ) as error:
            logger.error(f"POST {url} Error: {error}")

        channel.basic_ack(delivery_tag=method.delivery_tag)

        logger.info("CONSUMER - end")


def setup_channel(channel: BlockingChannel, queue_name: str, callback: Callable):  # pragma: no cover
    channel.queue_declare(queue=queue_name, durable=True)
    channel.queue_bind(queue=queue_name, exchange=settings.RABBITMQ_EXCHANGE)
    channel.basic_qos(prefetch_count=1)
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

    channel = None

    while True:
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
                    Callback(url=url).callback,
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
            sleep(ITER_SLEEP)
