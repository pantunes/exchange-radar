import logging

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import (
    AMQPConnectionError,
    ChannelWrongStateError,
    ConnectionClosedByBroker,
    StreamLostError,
)

from exchange_radar.producer.enums import Ranking
from exchange_radar.producer.schemas.binance import BinanceTradeSchema
from exchange_radar.producer.schemas.coinbase import CoinbaseTradeSchema
from exchange_radar.producer.schemas.kucoin import KucoinTradeSchema
from exchange_radar.producer.settings import base as settings
from exchange_radar.producer.utils import get_ranking

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO if settings.DEBUG else logging.WARNING)

logging.getLogger("pika").propagate = False


class ProducerConnection:
    connection = None
    channel = None

    def get_connection(self) -> pika.BlockingConnection:
        if self.connection and self.connection.is_open:
            logger.info("Reusing connection...")
            return self.connection

        credentials = pika.PlainCredentials(
            settings.RABBITMQ_DEFAULT_USER, settings.RABBITMQ_DEFAULT_PASS
        )

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

    def get_channel(self, queue_name) -> BlockingChannel:
        if self.channel and self.channel.is_open:
            logger.info("Reusing channel...")
            return self.channel

        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=queue_name, durable=True)

        return self.channel


class ProducerChannel:
    def __init__(self, queue_name):
        self.connection = producer_connection.get_connection()
        self.queue_name = queue_name

    def __enter__(self) -> BlockingChannel:
        return producer_connection.get_channel(self.queue_name)

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


producer_connection = ProducerConnection()


def publish(data: BinanceTradeSchema | KucoinTradeSchema | CoinbaseTradeSchema) -> None:
    logger.info(f"PUB: {data.trade_time} {data.symbol}")

    try:
        with ProducerChannel(queue_name=settings.RABBITMQ_TRADES_QUEUE_NAME) as channel:
            channel.basic_publish(
                exchange=settings.RABBITMQ_EXCHANGE,
                routing_key=settings.RABBITMQ_TRADES_QUEUE_NAME,
                body=data.model_dump_json().encode(),
                properties=pika.BasicProperties(
                    delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE
                ),
            )

        queue_name = None
        if get_ranking(data) == Ranking.WHALE:
            queue_name = settings.RABBITMQ_TRADES_WHALES_QUEUE_NAME
        elif get_ranking(data) == Ranking.DOLPHIN:
            queue_name = settings.RABBITMQ_TRADES_DOLPHIN_QUEUE_NAME
        elif get_ranking(data) == Ranking.OCTOPUS:
            queue_name = settings.RABBITMQ_TRADES_OCTOPUS_QUEUE_NAME

        if queue_name is not None:
            with ProducerChannel(queue_name=queue_name) as channel:
                channel.basic_publish(
                    exchange=settings.RABBITMQ_EXCHANGE,
                    routing_key=queue_name,
                    body=data.model_dump_json().encode(),
                    properties=pika.BasicProperties(
                        delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE
                    ),
                )
    except (
        StreamLostError,
        ConnectionClosedByBroker,
        ChannelWrongStateError,
    ) as error:
        logger.error(f"ERROR: {error}")
    except AMQPConnectionError:
        logger.error("ERROR: General AMQP Connection Error")
    except Exception as error:
        logger.error(f"ERROR: {error}")
    else:
        logger.info(f"PUB OK: {data.trade_time} {data.symbol}")
