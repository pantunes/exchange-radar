from exchange_radar.producer.enums import Ranking
from exchange_radar.producer.schemas.binance import BinanceTradeSchema
from exchange_radar.producer.schemas.kucoin import KucoinTradeSchema


def get_ranking(data: BinanceTradeSchema | KucoinTradeSchema) -> Ranking | None:
    if data.currency in (
        "USDT",
        "BUSD",
        "USD",
    ):
        if data.total > 100000.0:
            return Ranking.WHALE
        if data.total > 10000.0:
            return Ranking.DOLPHIN
        if data.total > 1000.0:
            return Ranking.OCTOPUS
        return

    if data.currency == "BTC":
        if data.total > 4.0:
            return Ranking.WHALE
        if data.total > 0.4:
            return Ranking.DOLPHIN
        if data.total > 0.04:
            return Ranking.OCTOPUS
        return

    if data.currency == "ETH":
        if data.total > 60.0:
            return Ranking.WHALE
        if data.total > 6.0:
            return Ranking.DOLPHIN
        if data.total > 0.6:
            return Ranking.OCTOPUS
        return

    raise ValueError(f"Currency not configured {data.currency}")
