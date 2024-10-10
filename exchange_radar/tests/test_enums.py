from exchange_radar.producer.enums import Ranking as RankingProducer
from exchange_radar.web.src.enums import Ranking as RankingWeb


def test_enums():
    assert RankingWeb.choices() == RankingProducer.choices()
