from exchange_radar.producer.tasks.binance import BinanceTradesTask
from exchange_radar.producer.tasks.coinbase import CoinbaseTradesTask
from exchange_radar.producer.tasks.kraken import KrakenTradesTask
from exchange_radar.producer.tasks.kucoin import KuCoinTradesTask
from exchange_radar.producer.tasks.okx import OkxTradesTask

EXCHANGES = {
    "binance": BinanceTradesTask,
    "kucoin": KuCoinTradesTask,
    "coinbase": CoinbaseTradesTask,
    "kraken": KrakenTradesTask,
    "okx": OkxTradesTask,
}
