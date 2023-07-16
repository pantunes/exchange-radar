import datetime
from decimal import Decimal

from exchange_radar.producer.schemas.binance import BinanceTradeSchema
from exchange_radar.producer.schemas.coinbase import CoinbaseTradeSchema
from exchange_radar.producer.schemas.kucoin import KucoinTradeSchema


def test_schemas_binance():
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

    payload = BinanceTradeSchema(**msg)

    assert payload.model_dump() == {
        "symbol": "BNBBTC",
        "price": Decimal("0.001"),
        "quantity": Decimal("100"),
        "trade_time": datetime.datetime(2022, 12, 31, 19, 43, 2),
        "is_seller": True,
        "total": Decimal("0.100"),
        "currency": "BTC",
        "trade_symbol": "BNB",
        "message": "2022-12-31 19:43:02 | <span class='binance'>Binance </span> |     0.00100000  BTC |"
        "           100.00000000 BNB |        0.10000000  BTC",
        "message_with_keys": "2022-12-31 19:43:02 | Binance  |      PRICE: 0.00100000 BTC |"
        "           QTY: 100.00000000 BNB |         TOTAL: 0.10000000 BTC",
        "exchange": "Binance",
    }


def test_schemas_kucoin():
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

    payload = KucoinTradeSchema(**msg["data"])

    assert payload.model_dump() == {
        "symbol": "LTOBTC",
        "price": Decimal("0.000003518"),
        "quantity": Decimal("3.7335"),
        "trade_time": datetime.datetime(2023, 5, 3, 10, 10, 39),
        "total": Decimal("0.0000131344530"),
        "currency": "BTC",
        "trade_symbol": "LTO",
        "message": "2023-05-03 10:10:39 | <span class='kucoin'>Kucoin  </span> |     0.00000352  BTC |"
        "             3.73350000 LTO |        0.00001313  BTC",
        "message_with_keys": "2023-05-03 10:10:39 | Kucoin   |      PRICE: 0.00000352 BTC |"
        "             QTY: 3.73350000 LTO |         TOTAL: 0.00001313 BTC",
        "is_seller": True,
        "exchange": "Kucoin",
    }


def test_schemas_coinbase():
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

    payload = CoinbaseTradeSchema(**msg)

    assert payload.model_dump() == {
        "symbol": "ETHUSD",
        "price": Decimal("1933.93"),
        "quantity": Decimal("0.00251665"),
        "trade_time": datetime.datetime(2023, 7, 16, 12, 19, 57),
        "total": Decimal("4.8670249345"),
        "currency": "USD",
        "trade_symbol": "ETH",
        "message": "2023-07-16 12:19:57 | <span class='coinbase'>Coinbase</span> |  1933.93000000  USD |"
        "             0.00251665 ETH |        4.86702493  USD",
        "message_with_keys": "2023-07-16 12:19:57 | Coinbase |   PRICE: 1933.93000000 USD |"
        "             QTY: 0.00251665 ETH |         TOTAL: 4.86702493 USD",
        "is_seller": True,
        "exchange": "Coinbase",
    }
