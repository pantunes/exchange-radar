from exchange_radar.web.src.types import ERdefaultdict


def test_erdefaultdict():
    d = ERdefaultdict(list)

    d["key"] = [1, 2, 3, 4, 5]
    assert repr(d) == "ERdefaultdict(<class 'list'>, {'key': [1, 2, 3, 4, 5]})"


def test_erdefaultdict__operations():
    d = ERdefaultdict(list)

    d.__get__(coin="BTC", category="One").append("A")
    assert repr(d) == "ERdefaultdict(<class 'list'>, {'BTC-One': ['A']})"
    d.__get__(coin="BTC", category="One").append("B")
    assert repr(d) == "ERdefaultdict(<class 'list'>, {'BTC-One': ['A', 'B']})"

    assert d.__get__(coin="BTC", category="One").pop(0) == "A"
    assert d.__get__(coin="BTC", category="One").pop(0) == "B"

    assert len(d.__get__(coin="BTC", category="One")) == 0
    assert len(d["BTC-One"]) == 0


def test_erdefaultdict__exclusivity():
    d = ERdefaultdict(list)

    d.__get__(coin="BTC", category="One").append("A")
    assert repr(d) == "ERdefaultdict(<class 'list'>, {'BTC-One': ['A']})"
    d.__get__(coin="BTC", category="Two").append("B")
    assert repr(d) == "ERdefaultdict(<class 'list'>, {'BTC-One': ['A'], 'BTC-Two': ['B']})"
