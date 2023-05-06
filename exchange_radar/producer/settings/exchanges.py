from exchange_radar.producer.tasks.binance import BinanceTradesTask
from exchange_radar.producer.tasks.kucoin import KucoinTradesTask

EXCHANGES = {
    "Binance": BinanceTradesTask,
    "Kucoin": KucoinTradesTask,
}
