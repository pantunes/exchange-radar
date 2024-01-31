import datetime
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from exchange_radar.producer.serializers.binance import BinanceTradeSerializer
from exchange_radar.producer.serializers.bitstamp import BitstampTradeSerializer
from exchange_radar.producer.serializers.bybit import BybitTradeSerializer
from exchange_radar.producer.serializers.coinbase import CoinbaseTradeSerializer
from exchange_radar.producer.serializers.htx import HtxTradeSerializer
from exchange_radar.producer.serializers.kraken import KrakenTradeSerializer
from exchange_radar.producer.serializers.kucoin import KucoinTradeSerializer
from exchange_radar.producer.serializers.mexc import MexcTradeSerializer
from exchange_radar.producer.serializers.okx import OkxTradeSerializer


@patch("exchange_radar.producer.models.redis")
def test_serializer_binance(mock_redis):
    mock_redis.hincrbyfloat.return_value = 100.0
    mock_redis.pipeline().__enter__().execute = MagicMock(return_value=[1.0, 100.0])

    msg = {
        "e": "trade",  # Event type
        "E": 1672515782136,  # Event time
        "s": "BNBBTC",  # Symbol
        "t": 12345,  # Trade ID
        "p": "0.001",  # Price
        "q": "100",  # Quantity
        "b": 88,  # Buyer order ID
        "a": 50,  # Seller order ID
        "T": 1672515782136,  # Trade time
        "m": True,  # Is the buyer the market maker?
        "M": True,  # Ignore
    }

    payload = BinanceTradeSerializer(**msg)

    assert payload.model_dump() == {
        "symbol": "BNBBTC",
        "price": Decimal("0.001"),
        "quantity": Decimal("100"),
        "trade_time": datetime.datetime(2022, 12, 31, 19, 43, 2),
        "trade_time_ts": 1672515782,
        "is_seller": True,
        "total": Decimal("0.100"),
        "currency": "BTC",
        "trade_symbol": "BNB",
        "message": "2022-12-31 19:43:02 | <span class='binance'>Binance </span> |     0.00100000  BTC |"
        "           100.00000000 BNB |        0.10000000  BTC",
        "number_trades": (
            1,
            100,
        ),
        "exchange": "Binance",
        "volume": 100.0,
        "volume_trades": (
            1.0,
            100.0,
        ),
    }


@patch("exchange_radar.producer.models.redis")
def test_serializer_kucoin(mock_redis):
    mock_redis.hincrbyfloat.return_value = 3.7335
    mock_redis.pipeline().__enter__().execute = MagicMock(return_value=[1.0, 100.0])

    msg = {
        "type": "message",
        "topic": "/market/match:LTO-BTC",
        "subject": "trade.l3match",
        "data": {
            "makerOrderId": "645232761893ff000144c526",
            "price": "0.000003518",
            "sequence": "3207633495398401",
            "side": "sell",
            "size": "3.7335",
            "symbol": "LTO-BTC",
            "takerOrderId": "6452331f702d43000133d018",
            "time": "1683108639912000000",
            "tradeId": "3207633495398401",
            "type": "match",
        },
    }

    payload = KucoinTradeSerializer(**msg["data"])

    assert payload.model_dump() == {
        "symbol": "LTOBTC",
        "price": Decimal("0.000003518"),
        "quantity": Decimal("3.7335"),
        "trade_time": datetime.datetime(2023, 5, 3, 10, 10, 39),
        "trade_time_ts": 1683108639,
        "total": Decimal("0.0000131344530"),
        "currency": "BTC",
        "trade_symbol": "LTO",
        "message": "2023-05-03 10:10:39 | <span class='kucoin'>KuCoin  </span> |     0.00000352  BTC |"
        "             3.73350000 LTO |        0.00001313  BTC",
        "number_trades": (
            1,
            100,
        ),
        "is_seller": True,
        "exchange": "KuCoin",
        "volume": 3.7335,
        "volume_trades": (
            1.0,
            100.0,
        ),
    }


@patch("exchange_radar.producer.models.redis")
def test_serializer_coinbase(mock_redis):
    mock_redis.hincrbyfloat.return_value = 0.00251665
    mock_redis.pipeline().__enter__().execute = MagicMock(return_value=[1.0, 100.0])

    msg = {
        "type": "last_match",
        "trade_id": 461948687,
        "maker_order_id": "335d96b3-e77a-411b-924c-a6acbbe8affb",
        "taker_order_id": "ebe2f71e-513a-4084-97d1-4d5809be161b",
        "side": "sell",
        "size": "0.00251665",
        "price": "1933.93",
        "product_id": "ETH-USD",
        "sequence": 47388972940,
        "time": "2023-07-16T12:19:57.255067Z",
    }

    payload = CoinbaseTradeSerializer(**msg)

    assert payload.model_dump() == {
        "symbol": "ETHUSD",
        "price": Decimal("1933.93"),
        "quantity": Decimal("0.00251665"),
        "trade_time": datetime.datetime(2023, 7, 16, 12, 19, 57),
        "trade_time_ts": 1689509997,
        "total": Decimal("4.8670249345"),
        "currency": "USD",
        "trade_symbol": "ETH",
        "message": "2023-07-16 12:19:57 | <span class='coinbase'>Coinbase</span> |  1933.93000000  USD |"
        "             0.00251665 ETH |        4.86702493  USD",
        "number_trades": (
            1,
            100,
        ),
        "is_seller": True,
        "exchange": "Coinbase",
        "volume": 0.00251665,
        "volume_trades": (
            1.0,
            100.0,
        ),
    }


@patch("exchange_radar.producer.models.redis")
def test_serializer_kraken(mock_redis):
    mock_redis.hincrbyfloat.return_value = 0.03409475
    mock_redis.pipeline().__enter__().execute = MagicMock(return_value=[1.0, 100.0])

    msg = [
        337,
        [["29911.20000", "0.03409475", "1690115020.186705", "s", "l", ""]],
        "trade",
        "XBT/USD",
    ]

    _, trades, _, symbol = msg
    trade = trades[0]

    price, volume, time, side, order_type, misc = trade

    payload = KrakenTradeSerializer(
        symbol=symbol,
        price=price,
        quantity=volume,
        trade_time=time,
        side=side,
    )

    assert payload.model_dump() == {
        "symbol": "BTCUSD",
        "price": Decimal("29911.20000"),
        "quantity": Decimal("0.03409475"),
        "trade_time": datetime.datetime(2023, 7, 23, 12, 23, 40),
        "trade_time_ts": 1690115020,
        "total": Decimal("1019.8148862000"),
        "currency": "USD",
        "trade_symbol": "BTC",
        "message": "2023-07-23 12:23:40 | <span class='kraken'>Kraken  </span> | 29911.20000000  USD |"
        "             0.03409475 BTC |     1019.81488620  USD",
        "number_trades": (
            1,
            100,
        ),
        "is_seller": True,
        "exchange": "Kraken",
        "volume": 0.03409475,
        "volume_trades": (
            1.0,
            100.0,
        ),
    }


@patch("exchange_radar.producer.models.redis")
def test_serializer_okx(mock_redis):
    mock_redis.hincrbyfloat.return_value = 3.7335
    mock_redis.pipeline().__enter__().execute = MagicMock(return_value=[1.0, 100.0])

    msg = (
        '{"arg": {"channel": "trades-all", "instId": "BTC-USDT"}, '
        '"data": [{"instId": "BTC-USDT", "tradeId": "474908816", "px": "42963.9", '
        '"sz": "0.00021505", "side": "sell", "ts": "1705350981085"}]}'
    )

    payload = OkxTradeSerializer(**json.loads(msg)["data"][0])

    assert payload.model_dump() == {
        "symbol": "BTCUSDT",
        "price": Decimal("42963.9"),
        "quantity": Decimal("0.00021505"),
        "trade_time": datetime.datetime(2024, 1, 15, 20, 36, 21),
        "total": Decimal("9.239386695"),
        "currency": "USDT",
        "trade_symbol": "BTC",
        "volume": 3.7335,
        "volume_trades": (
            1.0,
            100.0,
        ),
        "number_trades": (
            1,
            100,
        ),
        "trade_time_ts": 1705350981,
        "message": "2024-01-15 20:36:21 | <span class='okx'>OKX     </span> | 42963.90000000 USDT |"
        "             0.00021505 BTC |        9.23938670 USDT",
        "exchange": "OKX",
        "is_seller": True,
    }


@patch("exchange_radar.producer.models.redis")
def test_serializer_bybit(mock_redis):
    mock_redis.hincrbyfloat.return_value = 3.7335
    mock_redis.pipeline().__enter__().execute = MagicMock(return_value=[1.0, 100.0])

    msg = {
        "i": "2280000000179998536",
        "T": 1706016564433,
        "p": "2211.18",
        "v": "0.00268",
        "S": "Buy",
        "s": "ETHUSDT",
        "BT": False,
    }

    payload = BybitTradeSerializer(**msg)

    assert payload.model_dump() == {
        "symbol": "ETHUSDT",
        "price": Decimal("2211.18"),
        "quantity": Decimal("0.00268"),
        "trade_time": datetime.datetime(2024, 1, 23, 13, 29, 24),
        "total": Decimal("5.9259624"),
        "currency": "USDT",
        "trade_symbol": "ETH",
        "volume": 3.7335,
        "volume_trades": (1.0, 100.0),
        "number_trades": (1, 100),
        "trade_time_ts": 1706016564,
        "message": "2024-01-23 13:29:24 | <span class='bybit'>Bybit   </span> |  2211.18000000 USDT |"
        "             0.00268000 ETH |        5.92596240 USDT",
        "exchange": "Bybit",
        "is_seller": False,
    }


@patch("exchange_radar.producer.models.redis")
def test_serializer_bitstamp(mock_redis):
    mock_redis.hincrbyfloat.return_value = 3.7335
    mock_redis.pipeline().__enter__().execute = MagicMock(return_value=[1.0, 100.0])

    msg = (
        '{"data": {"id": 317421548, "timestamp": "1706398070", "amount": 0.0116, "amount_str": "0.01160000", '
        '"price": 2266.7, "price_str": "2266.7", "type": 0, "microtimestamp": "1706398070601000", '
        '"buy_order_id": 1710338440986624, "sell_order_id": 1710338436296705}, "channel": "live_trades_ethusd", '
        '"event": "trade"}'
    )
    msg = json.loads(msg)
    msg["data"]["channel"] = msg["channel"]

    payload = BitstampTradeSerializer(**msg["data"])

    assert payload.model_dump() == {
        "symbol": "ETHUSD",
        "price": Decimal("2266.7"),
        "quantity": Decimal("0.01160000"),
        "trade_time": datetime.datetime(2024, 1, 27, 23, 27, 50),
        "total": Decimal("26.293720000"),
        "currency": "USD",
        "trade_symbol": "ETH",
        "volume": 3.7335,
        "volume_trades": (1.0, 100.0),
        "number_trades": (1, 100),
        "trade_time_ts": 1706398070,
        "message": "2024-01-27 23:27:50 | <span class='bitstamp'>Bitstamp</span> |  2266.70000000  USD |"
        "             0.01160000 ETH |       26.29372000  USD",
        "exchange": "Bitstamp",
        "is_seller": False,
    }


@patch("exchange_radar.producer.models.redis")
def test_serializer_mexc(mock_redis):
    mock_redis.hincrbyfloat.return_value = 3.7335
    mock_redis.pipeline().__enter__().execute = MagicMock(return_value=[1.0, 100.0])

    msg = {
        "c": "spot@public.deals.v3.api@BTCUSDT",
        "d": {
            "deals": [{"p": "43469.99", "v": "0.002153", "S": 1, "t": 1706615234824}],
            "e": "spot@public.deals.v3.api",
        },
        "s": "BTCUSDT",
        "t": 1706615234826,
    }

    _msg = msg["d"]["deals"][0]
    _msg.update({"s": msg["s"]})
    payload = MexcTradeSerializer(**_msg)

    assert payload.model_dump() == {
        "symbol": "BTCUSDT",
        "price": Decimal("43469.99"),
        "quantity": Decimal("0.002153"),
        "trade_time": datetime.datetime(2024, 1, 30, 11, 47, 14),
        "total": Decimal("93.59088847"),
        "currency": "USDT",
        "trade_symbol": "BTC",
        "volume": 3.7335,
        "volume_trades": (1.0, 100.0),
        "number_trades": (1, 100),
        "trade_time_ts": 1706615234,
        "message": "2024-01-30 11:47:14 | <span class='mexc'>MEXC    </span> | 43469.99000000 USDT |"
        "             0.00215300 BTC |       93.59088847 USDT",
        "exchange": "MEXC",
        "is_seller": False,
    }


@patch("exchange_radar.producer.models.redis")
def test_serializer_htx(mock_redis):
    mock_redis.hincrbyfloat.return_value = 3.7335
    mock_redis.pipeline().__enter__().execute = MagicMock(return_value=[1.0, 100.0])

    msg = {
        "id": 116629582655996198945167846,
        "ts": 1706698561897,
        "tradeId": 100267772152,
        "amount": 16.72,
        "price": 15.4841,
        "direction": "buy",
        "channel": "market.linkusdt.trade.detail",
    }
    payload = HtxTradeSerializer(**msg)

    assert payload.model_dump() == {
        "symbol": "LINKUSDT",
        "price": Decimal("15.4841"),
        "quantity": Decimal("16.72"),
        "trade_time": datetime.datetime(2024, 1, 31, 10, 56, 1),
        "total": Decimal("258.894152"),
        "currency": "USDT",
        "trade_symbol": "LINK",
        "volume": 3.7335,
        "volume_trades": (1.0, 100.0),
        "number_trades": (1, 100),
        "trade_time_ts": 1706698561,
        "message": "2024-01-31 10:56:01 | <span class='htx'>HTX     </span> |    15.48410000 USDT |"
        "           16.72000000 LINK |      258.89415200 USDT",
        "is_seller": False,
        "exchange": "HTX",
    }
