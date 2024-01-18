from unittest.mock import Mock

import pytest


@pytest.fixture
def channel():
    return Mock()


@pytest.fixture
def method():
    method = Mock()
    method.consumer_tag = "ctag24.1234567890"
    method.delivery_tag = 32424
    method.redelivered = False
    return method


@pytest.fixture
def properties():
    properties = Mock()
    properties.headers = None
    return properties
