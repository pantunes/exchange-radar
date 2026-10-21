import json
import logging
from unittest.mock import Mock

import pytest
import requests
from pika.exceptions import StreamLostError

from exchange_radar.consumer import delivery
from exchange_radar.consumer.main import setup_channel
from exchange_radar.feed import FEED_BATCH_WAIT, MAX_FEED_BATCH_SIZE


@pytest.fixture
def handler():
    session = Mock()
    session.post.return_value.json.side_effect = lambda: {"accepted": len(session.post.call_args.kwargs["json"])}
    return delivery.Callback("http://web/api/feed/{coin}", session)


def deliver(handler, channel, trade_id, symbol="BTC"):
    body = json.dumps({"trade_symbol": symbol, "id": trade_id}).encode()
    handler.callback(channel, Mock(delivery_tag=trade_id), None, body)


def test_full_batch_uses_one_request_in_delivery_order(handler, channel):
    for trade_id in range(MAX_FEED_BATCH_SIZE):
        deliver(handler, channel, trade_id, "BTC" if trade_id % 2 else "ETH")
    handler.session.post.assert_called_once()
    request = handler.session.post.call_args.kwargs
    assert request["url"] == "http://web/api/feed/_batch"
    assert [data["id"] for data in request["json"]] == list(range(MAX_FEED_BATCH_SIZE))
    assert [call.kwargs for call in channel.basic_ack.call_args_list] == [
        {"delivery_tag": trade_id} for trade_id in range(MAX_FEED_BATCH_SIZE)
    ]
    assert handler.pending == []
    channel.connection.remove_timeout.assert_called_once()


def test_partial_batch_waits_for_timer_and_is_not_acknowledged_early(handler, channel):
    deliver(handler, channel, 1)
    handler.session.post.assert_not_called()
    channel.basic_ack.assert_not_called()
    delay, flush = channel.connection.call_later.call_args.args
    assert delay == FEED_BATCH_WAIT
    flush()
    handler.session.post.assert_called_once()
    channel.basic_ack.assert_called_once_with(delivery_tag=1)


@pytest.mark.parametrize(
    "error", [requests.Timeout("slow"), requests.ConnectionError("offline"), requests.HTTPError("500")]
)
def test_failed_request_retains_batch_until_retry_succeeds(handler, channel, error):
    deliver(handler, channel, 1)
    handler.session.post.side_effect = error
    handler.flush()
    channel.basic_ack.assert_not_called()
    assert len(handler.pending) == 1
    assert channel.connection.call_later.call_args.args[0] == 1
    handler.session.post.side_effect = None
    handler.flush()
    channel.basic_ack.assert_called_once_with(delivery_tag=1)
    assert handler.pending == []
    assert handler.retry_delay == 1
    assert not handler.retrying


def test_unsuccessful_http_status_is_not_acknowledged(handler, channel):
    deliver(handler, channel, 1)
    handler.session.post.return_value.raise_for_status.side_effect = requests.HTTPError("503")
    handler.flush()
    channel.basic_ack.assert_not_called()
    assert handler.pending[0][0] == 1


def test_failure_backoff_is_capped_and_new_deliveries_do_not_bypass_it(handler, channel):
    deliver(handler, channel, 0)
    handler.session.post.side_effect = requests.Timeout("slow")
    delays = []
    for _ in range(6):
        handler.flush()
        delays.append(channel.connection.call_later.call_args.args[0])
    assert delays == [1, 2, 4, 8, 10, 10]
    attempts = handler.session.post.call_count
    for trade_id in range(1, MAX_FEED_BATCH_SIZE):
        deliver(handler, channel, trade_id)
    assert handler.session.post.call_count == attempts
    assert len(handler.pending) == MAX_FEED_BATCH_SIZE


def test_acknowledgements_do_not_cover_other_queue_callbacks(handler, channel):
    whales = delivery.Callback("http://web/api/feed/{coin}/whales", handler.session)
    deliver(handler, channel, 1)
    deliver(whales, channel, 2)
    deliver(handler, channel, 3)
    handler.flush()
    assert [call.kwargs for call in channel.basic_ack.call_args_list] == [{"delivery_tag": 1}, {"delivery_tag": 3}]
    assert whales.pending[0][0] == 2


def test_lost_amqp_ack_keeps_deliveries_available_for_redelivery(handler, channel):
    deliver(handler, channel, 1)
    channel.basic_ack.side_effect = StreamLostError("lost")
    with pytest.raises(StreamLostError):
        handler.flush()
    assert handler.pending[0][0] == 1


def test_empty_flush_does_not_send_or_acknowledge(handler, channel):
    handler.flush()
    handler.session.post.assert_not_called()
    channel.basic_ack.assert_not_called()


@pytest.mark.parametrize("body", [b"not-json", b"[]", b"{}", b'{"trade_symbol": 12}', b'{"trade_symbol": ""}'])
def test_malformed_delivery_is_not_acknowledged(handler, channel, body):
    with pytest.raises(ValueError):
        handler.callback(channel, Mock(delivery_tag=1), None, body)
    channel.basic_ack.assert_not_called()
    assert handler.pending == []


def test_prefetch_bounds_each_queues_unacknowledged_batch(channel):
    callback = Mock()
    setup_channel(channel, "trades", callback)
    channel.basic_qos.assert_called_once_with(prefetch_count=MAX_FEED_BATCH_SIZE)
    channel.basic_consume.assert_called_once_with(queue="trades", on_message_callback=callback)


def test_throughput_report_counts_delivered_messages_and_requests(handler, channel, monkeypatch, caplog):
    monkeypatch.setattr(delivery, "monotonic", Mock(return_value=61))
    handler.last_report = 0
    caplog.set_level(logging.INFO)
    deliver(handler, channel, 1)
    deliver(handler, channel, 2)
    handler.flush()
    assert "delivered=2 http_requests=1 pending=0" in caplog.text


@pytest.mark.parametrize("receipt", [{"r": False}, {"accepted": 0}, {"accepted": 2}, None, []])
def test_incompatible_or_incomplete_web_receipt_is_not_acknowledged(handler, channel, receipt):
    deliver(handler, channel, 1)
    handler.session.post.return_value.json.side_effect = None
    handler.session.post.return_value.json.return_value = receipt
    handler.flush()
    channel.basic_ack.assert_not_called()
    assert handler.pending[0][0] == 1
    assert handler.retrying
