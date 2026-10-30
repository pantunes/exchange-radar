import re
from types import SimpleNamespace
from unittest.mock import patch

from exchange_radar.web.src.models import Alerts


def test_alert_rows_align_new_labels_with_historical_names(client):
    records = [
        SimpleNamespace(
            time_ts=1792924800,
            price=2451.79,
            currency="USDT",
            name=name,
            message=message,
        )
        for name, message in (
            ("Price change ≥1% · 1 min · up/down", "Price decreased 2.07% over 1 min."),
            ("Price change ≥2% · 10 min · up/down", "Price increased 3.42% over 11 mins."),
            ("price-change-1-min", "The PRICE decreased 2.07% in the last 1 minute(s)"),
            ("price-change-10-min", "The PRICE increased 3.42% in the last 10 minute(s)"),
            ("Custom alert", "Price unchanged."),
        )
    ]
    with patch.object(Alerts, "find") as find:
        find.return_value.sort_by.return_value = records
        response = client.get("/api/alerts/ETH")

    assert response.status_code == 200
    rows = response.json()["rows"]
    page = client.get("/alerts/ETH")
    assert page.status_code == 200
    header = re.search(r"^.*<b>DATETIME UTC.*$", page.text, re.MULTILINE).group()
    header = header.replace("<b>", "").replace("</b>", "")
    for row, record in zip(rows, records):
        row = re.sub(r"</?span[^>]*>", "", row)
        assert row.split(" | ")[3].strip() == record.name
        assert row.split(" | ")[4] == record.message
        assert [i for i, char in enumerate(row) if char == "|"] == [i for i, char in enumerate(header) if char == "|"]

    for row, color_class in zip(rows, ("order_sell", "order_buy", "order_sell", "order_buy", None)):
        cells = row.split(" | ")
        if color_class:
            for index in (2, 4):
                assert cells[index].startswith(f"<span class='{color_class}'>")
                assert cells[index].endswith("</span>")
        else:
            assert "<span" not in row
