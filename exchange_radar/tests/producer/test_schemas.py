import datetime
from decimal import Decimal

from exchange_radar.producer.schemas.binance import BinanceTradeSchema
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
        "exchange": "Binance",
        "message": "2022-12-31 19:43:02 | Binance  |      0.00100000 BTC |           100.00000000 BNB |"
        "         0.10000000 BTC",
        "message_with_keys": "2022-12-31 19:43:02 | Binance  |      PRICE: 0.00100000 BTC |     "
        "      QTY: 100.00000000 BNB |         TOTAL: 0.10000000 BTC",
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
        "is_seller": True,
        "currency": "BTC",
        "trade_symbol": "LTO",
        "exchange": "Kucoin",
        "message": "2023-05-03 10:10:39 | Kucoin   |      0.00000352 BTC |             3.73350000 LTO |"
        "         0.00001313 BTC",
        "message_with_keys": "2023-05-03 10:10:39 | Kucoin   |      PRICE: 0.00000352 BTC |       "
        "      QTY: 3.73350000 LTO |         TOTAL: 0.00001313 BTC",
    }
