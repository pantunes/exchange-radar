from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

with patch("redis.connection.ConnectionPool.get_connection"):
    # Import the entry point first because it registers the periodic tasks.
    import exchange_radar.scheduler.main  # noqa: F401
    from exchange_radar.scheduler.alerts import market_sentiment as alerts


def statistics(price="100", currency="USDT"):
    return ["1000", "600", "400", "6", "4", price, currency]


@pytest.fixture
def scheduler(monkeypatch):
    redis = MagicMock()
    pipe = redis.pipeline.return_value.__enter__.return_value
    model = MagicMock()
    monkeypatch.setattr(alerts, "redis", redis)
    monkeypatch.setattr(alerts, "Alerts", model)
    alerts.alerts_cache.clear()
    yield pipe, model
    alerts.alerts_cache.clear()


@pytest.mark.parametrize("config", [alerts.EachMinuteTaskConfig(), alerts.Each10MinutesTaskConfig()])
@pytest.mark.parametrize(
    "invalid",
    [
        [None] * 7,
        statistics(price="bad-price"),
        statistics(price="0"),
        statistics(price="-1"),
        statistics(price="NaN"),
        statistics(price="Infinity"),
        statistics(currency=None),
        [None, *statistics()[1:]],
    ],
)
def test_bad_coin_does_not_block_later_coins(scheduler, monkeypatch, config, invalid):
    pipe, model = scheduler
    monkeypatch.setattr(alerts, "COINS", ["BTC", "RETIRED", "ETH"])
    pipe.execute.side_effect = [statistics(), invalid, statistics(), statistics(), invalid, statistics(price="103")]

    alerts.task(config=config)
    model.assert_not_called()
    alerts.task(config=config)

    assert pipe.execute.call_count == 6
    model.assert_called_once()
    assert model.call_args.kwargs["trade_symbol"] == "ETH"
    assert model.call_args.kwargs["name"] == config.name
    assert "increased 3.00%" in model.call_args.kwargs["message"]
    model.return_value.save.return_value.expire.assert_called_once_with(num_seconds=86400 * alerts.REDIS_EXPIRATION)


def test_recovered_coin_starts_a_new_comparison_interval(scheduler, monkeypatch):
    pipe, model = scheduler
    monkeypatch.setattr(alerts, "COINS", ["ETH"])
    pipe.execute.side_effect = [statistics(), [None] * 7, statistics(price="120"), statistics(price="123")]
    config = alerts.EachMinuteTaskConfig()

    for _ in range(3):
        alerts.task(config=config)
    model.assert_not_called()

    alerts.task(config=config)
    model.assert_called_once()
    assert "increased 2.50%" in model.call_args.kwargs["message"]


@pytest.mark.parametrize(
    ("config", "price", "expected"),
    [
        (alerts.EachMinuteTaskConfig(), "100.5", None),
        (alerts.EachMinuteTaskConfig(), "98", "decreased 2.00%"),
        (alerts.Each10MinutesTaskConfig(), "101.5", None),
        (alerts.Each10MinutesTaskConfig(), "103", "increased 3.00%"),
    ],
)
def test_price_alert_thresholds(scheduler, monkeypatch, config, price, expected):
    pipe, model = scheduler
    monkeypatch.setattr(alerts, "COINS", ["ETH"])
    pipe.execute.side_effect = [statistics(), statistics(price=price)]
    alerts.task(config=config)
    alerts.task(config=config)
    if expected:
        model.assert_called_once()
        assert expected in model.call_args.kwargs["message"]
    else:
        model.assert_not_called()


def test_currency_change_resets_price_comparison(scheduler, monkeypatch):
    pipe, model = scheduler
    monkeypatch.setattr(alerts, "COINS", ["ETH"])
    pipe.execute.side_effect = [statistics(currency="BTC"), statistics(price="10000"), statistics(price="10300")]
    config = alerts.EachMinuteTaskConfig()
    alerts.task(config=config)
    alerts.task(config=config)
    model.assert_not_called()
    alerts.task(config=config)
    model.assert_called_once()
    assert "increased 3.00%" in model.call_args.kwargs["message"]


def test_missing_coin_drops_only_its_own_baseline(scheduler, monkeypatch):
    pipe, _ = scheduler
    monkeypatch.setattr(alerts, "COINS", ["ETH"])
    config = alerts.EachMinuteTaskConfig()
    key = f"{datetime.today().date():%Y-%m-%d} {config}"
    alerts.alerts_cache[key]["BTC"] = {"price": 100, "currency": "USDT"}
    alerts.alerts_cache[key]["ETH"] = {"price": 100, "currency": "USDT"}
    pipe.execute.return_value = [None] * 7
    alerts.task(config=config)
    assert alerts.alerts_cache[key] == {"BTC": {"price": 100, "currency": "USDT"}}
