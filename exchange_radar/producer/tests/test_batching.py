import json
import os
import uuid
from unittest.mock import Mock

import pytest
from pika.exceptions import AMQPConnectionError, StreamLostError
from redis import Redis

from exchange_radar.producer import batching, models, publisher
from exchange_radar.producer.serializers.binance import BinanceTradeSerializer


def trade(trade_id=1, symbol="BTCUSDT", quantity="1", seller=False, timestamp=1672515782136, price="2000"):
    return {"t": trade_id, "s": symbol, "p": price, "q": quantity, "T": timestamp, "m": seller}


def mock_store(*snapshots):
    client = Mock()
    client.register_script.return_value.return_value = json.dumps(snapshots)
    return batching.TradeStatsStore(client), client.register_script.return_value


def test_per_trade_snapshots_are_stable_and_published_once(monkeypatch):
    store, script = mock_store(["1", "1", None, 1, None], ["3", "1", "2", 1, 1])
    batch = batching.TradeBatch([trade(), trade(2, quantity="2", seller=True)])
    payloads = []
    monkeypatch.setattr(batching, "publish", lambda data, **kwargs: payloads.append(data.model_dump(mode="json")))
    batch.process(store)
    batch.process(store)
    assert script.call_count == 1
    assert len(payloads) == 2
    assert payloads[0]["volume"] == 1.0
    assert payloads[0]["volume_trades"] is None
    assert payloads[1]["volume_trades"] == [1.0, 2.0]
    assert payloads[1]["number_trades"] == [1, 1]
    assert payloads[1]["ranking"] == batch.trades[1].ranking.value
    assert "trade_id" not in payloads[1]
    assert batch.trades[0].model_dump(mode="json") == payloads[0]


def test_publish_retry_does_not_reapply_statistics_or_republish_successes(monkeypatch):
    store, script = mock_store(["1", "1", None, 1, None], ["2", "2", None, 2, None])
    batch = batching.TradeBatch([trade(), trade(2)])
    publish = Mock(side_effect=[None, AMQPConnectionError("lost"), None])
    monkeypatch.setattr(batching, "publish", publish)
    with pytest.raises(AMQPConnectionError):
        batch.process(store)
    batch.process(store)
    assert script.call_count == 1
    assert [call.args[0].trade_id for call in publish.call_args_list] == [1, 2, 2]


def test_duplicates_are_not_published(monkeypatch):
    store, script = mock_store(["1", "1", None, 1, None], False)
    batch = batching.TradeBatch([trade(), trade()])
    publish = Mock()
    monkeypatch.setattr(batching, "publish", publish)
    batch.process(store)
    batch.process(store)
    assert script.call_count == 1
    publish.assert_called_once_with(batch.trades[0], raise_on_error=True)


def test_invalid_trade_does_not_discard_valid_trades(monkeypatch):
    store, _ = mock_store(["1", "1", None, 1, None])
    batch = batching.TradeBatch([{}, trade(symbol="BTCINVALID"), trade()])
    publish = Mock()
    monkeypatch.setattr(batching, "publish", publish)
    batch.process(store)
    assert len(batch.trades) == 1
    publish.assert_called_once()


def test_unpersisted_deferred_statistics_cannot_write_individually():
    data = BinanceTradeSerializer(_defer_stats=True, **trade())
    for name in ("volume", "volume_trades", "number_trades"):
        with pytest.raises(RuntimeError, match="not been persisted"):
            getattr(data, name)


@pytest.mark.parametrize("error", [AMQPConnectionError("offline"), StreamLostError("lost"), ValueError("bad")])
def test_publisher_can_report_failures_to_batch_worker(monkeypatch, error):
    data = Mock()
    channel = Mock(side_effect=error)
    monkeypatch.setattr(publisher, "ProducerChannel", channel)
    publisher.publish(data)
    with pytest.raises(type(error)):
        publisher.publish(data, raise_on_error=True)


def test_reconnected_publisher_does_not_reuse_the_old_channel(monkeypatch):
    connection = publisher.ProducerConnection()
    connection.connection = Mock(is_open=False)
    connection.channel = Mock(is_open=True)
    replacement = Mock()
    monkeypatch.setattr(publisher.pika, "BlockingConnection", Mock(return_value=replacement))
    connection.get_connection()
    assert connection.get_channel() is replacement.channel.return_value


class NamespacedRedis:
    """Only create and remove keys owned by this test; never flush a database."""

    def __init__(self, client):
        self.client = client
        self.prefix = f"radar-test:{uuid.uuid4().hex}:"
        self.keys = set()

    def key(self, name):
        key = self.prefix + name
        self.keys.add(key)
        return key

    def register_script(self, source):
        script = self.client.register_script(source)

        def call(*, keys, args):
            return script(keys=[self.key(key) for key in keys], args=args)

        return call

    def pipeline(self):
        namespace = self

        class Pipeline:
            def __enter__(self):
                self.pipe = namespace.client.pipeline()
                return self

            def __exit__(self, *args):
                self.pipe.reset()

            def __getattr__(self, name):
                def command(*args, **kwargs):
                    if args:
                        args = (namespace.key(args[0]), *args[1:])
                    elif "name" in kwargs:
                        kwargs["name"] = namespace.key(kwargs["name"])
                    return getattr(self.pipe, name)(*args, **kwargs)

                return command

        return Pipeline()

    def __getattr__(self, name):
        def command(key, *args, **kwargs):
            return getattr(self.client, name)(self.key(key), *args, **kwargs)

        return command

    def close(self):
        if self.keys:
            self.client.unlink(*self.keys)


@pytest.fixture
def real_redis():
    url = os.environ.get("TEST_REDIS_URL")
    if not url:
        pytest.skip("Set TEST_REDIS_URL to run real Redis integration tests")
    client = Redis.from_url(url)
    namespaces = []

    def create():
        namespace = NamespacedRedis(client)
        namespaces.append(namespace)
        return namespace

    yield create
    for namespace in namespaces:
        namespace.close()
    client.close()


def test_real_redis_matches_legacy_statistics_for_every_trade(real_redis, monkeypatch):
    legacy, updated = real_redis(), real_redis()
    messages = [
        trade(1, quantity="0.00000001", price="99999.12345678"),
        trade(2, quantity="3", seller=True),
        trade(1, symbol="ETHUSDT", quantity="4", seller=True),
        trade(2, symbol="ETHUSDT", quantity="1.25"),
        trade(3, quantity="0.5", timestamp=1672615782136),
        trade(4, quantity="0.25", seller=True, timestamp=1672615782136),
    ]
    monkeypatch.setattr(models, "redis", legacy)
    expected = [BinanceTradeSerializer(**message).model_dump(mode="json") for message in messages]
    batch = batching.TradeBatch(messages)
    batching.TradeStatsStore(updated).apply(batch.trades, batch.token)
    actual = [data.model_dump(mode="json") for data in batch.trades]
    assert actual == expected
    for day in {data._name for data in batch.trades}:
        assert updated.hgetall(day) == legacy.hgetall(day)
    assert updated.hgetall("COINS") == legacy.hgetall("COINS")
    assert set(updated.hgetall("EXCHANGES")) == {b"BINANCE"}


def test_real_redis_deduplicates_per_symbol_and_handles_large_trade_ids(real_redis):
    client = real_redis()
    store = batching.TradeStatsStore(client)
    large = 2**63 - 10
    first = batching.TradeBatch([trade(large), trade(large + 1), trade(large + 1), trade(large - 1)])
    store.apply(first.trades, first.token)
    assert [data._duplicate for data in first.trades] == [False, False, True, True]
    second = batching.TradeBatch([trade(large + 1), trade(large + 2), trade(large, symbol="BTCETH", seller=True)])
    store.apply(second.trades, second.token)
    assert [data._duplicate for data in second.trades] == [True, False, False]
    assert client.hget(first.trades[0]._name, "BTC_VOLUME") == b"4"
    assert client.hget(first.trades[0]._name, "BTC_NUMBER_BUY_ORDERS") == b"3"
    assert client.hget(first.trades[0]._name, "BTC_NUMBER_SELL_ORDERS") == b"1"


def test_real_redis_retry_after_a_lost_reply_preserves_snapshots(real_redis):
    client = real_redis()
    store = batching.TradeStatsStore(client)
    original = store.script
    lost = False

    def lose_reply(**kwargs):
        nonlocal lost
        result = original(**kwargs)
        if not lost:
            lost = True
            raise ConnectionError("reply was lost after commit")
        return result

    store.script = lose_reply
    batch = batching.TradeBatch([trade(), trade(2, seller=True)])
    with pytest.raises(ConnectionError):
        store.apply(batch.trades, batch.token)
    store.apply(batch.trades, batch.token)
    assert [data.volume for data in batch.trades] == [1.0, 2.0]
    assert client.hget(batch.trades[0]._name, "BTC_VOLUME") == b"2"
    assert not any(data._duplicate for data in batch.trades)


def test_real_redis_sets_expiry_on_the_first_trade_of_a_day(real_redis):
    client = real_redis()
    batch = batching.TradeBatch([trade()])
    batching.TradeStatsStore(client).apply(batch.trades, batch.token)
    assert client.ttl(batch.trades[0]._name) > 0
    assert client.ttl(f"trades:seen:{batch.trades[0]._name}") > 0


def test_real_redis_batches_are_consistent_with_legacy_producers(real_redis, monkeypatch):
    client = real_redis()
    monkeypatch.setattr(models, "redis", client)
    store = batching.TradeStatsStore(client)
    first = batching.TradeBatch([trade()])
    store.apply(first.trades, first.token)
    legacy = BinanceTradeSerializer(**trade(10, quantity="2", seller=True))
    assert legacy.model_dump()["volume"] == 3.0
    last = batching.TradeBatch([trade(2, quantity="3")])
    store.apply(last.trades, last.token)
    assert last.trades[0].volume == 6.0
    assert last.trades[0].number_trades == (2, 1)


@pytest.mark.parametrize(
    "price, expected_route",
    [("100", None), ("2000", "trades.octopuses"), ("20000", "trades.dolphins"), ("200000", "trades.whales")],
)
def test_publisher_preserves_all_trades_and_ranked_alert_routes(monkeypatch, price, expected_route):
    store, _ = mock_store(["1", "1", None, 1, None])
    batch = batching.TradeBatch([trade(price=price)])
    store.apply(batch.trades, batch.token)
    connection = publisher.ProducerConnection()
    connection.connection = Mock(is_open=True)
    connection.channel = Mock(is_open=True)
    monkeypatch.setattr(publisher, "producer_connection", connection)
    publisher.publish(batch.trades[0], raise_on_error=True)
    calls = connection.channel.basic_publish.call_args_list
    assert [call.kwargs["routing_key"] for call in calls] == ["trades.all"] + (
        [expected_route] if expected_route else []
    )
    assert all(json.loads(call.kwargs["body"]) == batch.trades[0].model_dump(mode="json") for call in calls)
