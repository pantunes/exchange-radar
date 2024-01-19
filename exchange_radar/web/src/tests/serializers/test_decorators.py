from unittest.mock import MagicMock

import pytest
from starlette.exceptions import HTTPException, WebSocketException

from exchange_radar.web.src.serializers.decorators import ERException, validate
from exchange_radar.web.src.serializers.http import ParamsInputSerializer


@validate(serializer=ParamsInputSerializer)
async def f(request, data: ParamsInputSerializer):
    return data


@pytest.mark.asyncio
async def test_validate__no_request():
    assert await f(None) is None


@pytest.mark.parametrize("protocol", ["http", "websocket", "something"])
@pytest.mark.asyncio
async def test_validate(protocol):
    request = MagicMock()
    request.path_params = {"coin": "BTC"}
    request.scope = MagicMock()
    request.scope.__getitem__.return_value = protocol
    r = await f(request)
    assert r.coin == "BTC"


@pytest.mark.parametrize(
    "protocol, exc_class, expected",
    [
        (
            "http",
            HTTPException,
            "400: Mandatory fields are missing",
        ),
        (
            "websocket",
            WebSocketException,
            "1008: ",
        ),
        (
            "something",
            ERException,
            "400: Invalid request type",
        ),
    ],
)
@pytest.mark.asyncio
async def test_validate__errors(protocol, exc_class, expected):
    request = MagicMock()
    request.scope = MagicMock()
    request.scope.__getitem__.return_value = protocol
    with pytest.raises(exc_class) as exc_info:
        assert await f(request) is None
    assert str(exc_info.value) == expected


@pytest.mark.parametrize(
    "protocol, exc_class, expected",
    [
        (
            "http",
            HTTPException,
            "400: Invalid coin: BLAH",
        ),
        (
            "websocket",
            WebSocketException,
            "1008: ",
        ),
    ],
)
@pytest.mark.asyncio
async def test_validate__coin_errors(protocol, exc_class, expected):
    request = MagicMock()
    request.path_params = {"coin": "BLAH"}
    request.scope = MagicMock()
    request.scope.__getitem__.return_value = protocol
    with pytest.raises(exc_class) as exc_info:
        assert await f(request) is None
    assert str(exc_info.value) == expected


@pytest.mark.asyncio
async def test_validate__typeerror():
    request = MagicMock()
    request.scope = None
    with pytest.raises(ERException) as exc_info:
        assert await f(request) is None
    assert str(exc_info.value) == "400: Unset request type"
