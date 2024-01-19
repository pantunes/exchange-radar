import pytest

from exchange_radar.web.src.serializers.http import ParamsInputSerializer


def test_paramsinputserializer():
    obj = ParamsInputSerializer(coin="BTC")
    assert obj.coin == "BTC"


def test_paramsinputserializer__error():
    with pytest.raises(ValueError) as exc_info:
        ParamsInputSerializer(coin="BLAH")
    assert str(exc_info.value) == "Invalid coin: BLAH"
