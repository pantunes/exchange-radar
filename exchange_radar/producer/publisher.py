import logging

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import (
    AMQPConnectionError,
    ChannelWrongStateError,
    ConnectionClosedByBroker,
    StreamLostError,
)

from exchange_radar.producer.serializers.base import BaseSerializer
from exchange_radar.producer.settings import base as settings
from exchange_radar.producer.settings.routing_keys import ROUTING_KEYS
from exchange_radar.producer.utils import get_ranking

logger = logging.getLogger(__name__)

logging.getLogger("pika").propagate = False


class ProducerConnection:
    connection = None
    channel = None

    def get_connection(self) -> pika.BlockingConnection:
        if self.connection and self.connection.is_open:
            logger.info("Reusing connection...")
            return self.connection

        credentials = pika.PlainCredentials(settings.RABBITMQ_DEFAULT_USER, settings.RABBITMQ_DEFAULT_PASS)

        parameters = pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            credentials=credentials,
            virtual_host=settings.RABBITMQ_DEFAULT_VHOST,
            heartbeat=settings.RABBITMQ_CONNECTION_HEARTBEAT,
            blocked_connection_timeout=settings.RABBITMQ_BLOCKED_CONNECTION_TIMEOUT,
        )

        self.connection = pika.BlockingConnection(parameters)

        return self.connection

    def get_channel(self) -> BlockingChannel:
        if self.channel and self.channel.is_open:
            logger.info("Reusing channel...")
            return self.channel

        self.channel = self.connection.channel()
        return self.channel


class ProducerChannel:
    def __init__(self):
        self.connection = producer_connection.get_connection()

    def __enter__(self) -> BlockingChannel:
        return producer_connection.get_channel()

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


producer_connection = ProducerConnection()

params = {
    "exchange": settings.RABBITMQ_EXCHANGE,
    "properties": pika.BasicProperties(delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE),
}


def publish(data: BaseSerializer) -> None:
    logger.info(f"PRODUCER - start: {data.trade_time} {data.symbol}")

    body = data.model_dump_json().encode()

    try:
        with ProducerChannel() as channel:
            channel.basic_publish(routing_key=settings.RABBITMQ_TRADES_ROUTING_KEY, body=body, **params)

        try:
            queue_name = ROUTING_KEYS[get_ranking(data)]
        except KeyError:
            logger.info("No specific extra Queue")
        else:
            with ProducerChannel() as channel:
                channel.basic_publish(routing_key=queue_name, body=body, **params)
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
    else:
        logger.info(f"PRODUCER - end: {data.trade_time} {data.symbol}")
