import json
import logging
from time import monotonic

import requests

from exchange_radar.consumer.settings import base as settings
from exchange_radar.feed import FEED_BATCH_WAIT, MAX_FEED_BATCH_SIZE

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Callback:
    """Collect bounded deliveries and acknowledge only after successful HTTP delivery."""

    def __init__(self, url: str, session: requests.Session):
        self.url = url.format(coin="_batch")
        self.session = session
        self.pending = []
        self.channel = None
        self.timer = None
        self.retrying = False
        self.retry_delay = 1.0
        self.delivered = 0
        self.requests = 0
        self.last_report = monotonic()

    def callback(self, channel, method, properties, body):
        data = json.loads(body)
        if not isinstance(data, dict) or not isinstance(data.get("trade_symbol"), str) or not data["trade_symbol"]:
            raise ValueError("Trade must contain a nonempty trade_symbol")
        self.channel = channel
        self.pending.append((method.delivery_tag, data))
        if len(self.pending) >= MAX_FEED_BATCH_SIZE and not self.retrying:
            self.flush()
        elif self.timer is None:
            self.timer = channel.connection.call_later(FEED_BATCH_WAIT, self.flush)

    def flush(self):
        if self.timer is not None:
            self.channel.connection.remove_timeout(self.timer)
            self.timer = None
        if not self.pending:
            return

        # basic_qos limits each queue's outstanding deliveries to this batch size.
        batch = self.pending[:MAX_FEED_BATCH_SIZE]
        try:
            self.requests += 1
            response = self.session.post(
                url=self.url,
                json=[data for _, data in batch],
                timeout=(settings.POST_CONNECT_TIMEOUT, settings.POST_READ_TIMEOUT),
            )
            response.raise_for_status()
            receipt = response.json()
            if not isinstance(receipt, dict) or receipt.get("accepted") != len(batch):
                raise requests.exceptions.RequestException("Web service did not confirm complete batch acceptance")
        except requests.exceptions.RequestException as error:
            logger.warning("Feed batch POST %s failed: %s; retrying in %ss", self.url, error, self.retry_delay)
            self.retrying = True
            self.timer = self.channel.connection.call_later(self.retry_delay, self.flush)
            self.retry_delay = min(self.retry_delay * 2, 10.0)
            return

        for delivery_tag, _ in batch:
            # Different queues share the channel, so cumulative ACKs are unsafe.
            self.channel.basic_ack(delivery_tag=delivery_tag)
        del self.pending[: len(batch)]
        self.delivered += len(batch)
        self.retry_delay = 1.0
        self.retrying = False
        if self.pending:
            self.timer = self.channel.connection.call_later(FEED_BATCH_WAIT, self.flush)
        if monotonic() - self.last_report >= 60:
            logger.info(
                "Consumer throughput: endpoint=%s delivered=%s http_requests=%s pending=%s",
                self.url,
                self.delivered,
                self.requests,
                len(self.pending),
            )
            self.last_report = monotonic()
