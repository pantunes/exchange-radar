import re
from html.parser import HTMLParser

import pytest


class ScriptParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inline_scripts = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "script" and "src" not in attributes:
            self.inline_scripts.append(attributes)


@pytest.mark.parametrize(
    "path",
    ["/BTC", "/BTC/whales", "/BTC/dolphins", "/BTC/octopuses", "/history/BTC", "/alerts/BTC"],
)
def test_security_policy_allows_every_page_script(client, path):
    response = client.get(path)
    assert response.status_code == 200
    policy = response.headers["Content-Security-Policy"]
    nonce = re.search(r"'nonce-([^']+)'", policy).group(1)
    script_policy = next(part for part in policy.split(";") if part.strip().startswith("script-src"))
    assert "'unsafe-inline'" not in script_policy
    parser = ScriptParser()
    parser.feed(response.text)
    assert parser.inline_scripts
    assert all(script.get("nonce") == nonce for script in parser.inline_scripts)


def test_security_nonce_changes_between_responses(client):
    first = client.get("/BTC")
    second = client.get("/BTC")
    assert first.headers["Content-Security-Policy"] != second.headers["Content-Security-Policy"]


def test_validation_errors_receive_security_headers(client):
    response = client.get("/INVALID_COIN")
    assert response.status_code == 400
    assert "Content-Security-Policy" in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
