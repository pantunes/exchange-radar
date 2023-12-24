from exchange_radar.producer.tasks.binance import BinanceTradesTask
from exchange_radar.producer.tasks.coinbase import CoinbaseTradesTask
from exchange_radar.producer.tasks.kraken import KrakenTradesTask
from exchange_radar.producer.tasks.kucoin import KucoinTradesTask

EXCHANGES = {
    "Binance": BinanceTradesTask,
    "Kucoin": KucoinTradesTask,
    "Coinbase": CoinbaseTradesTask,
    "Kraken": KrakenTradesTask,
}
