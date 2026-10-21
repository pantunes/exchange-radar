from unittest.mock import Mock

import pytest
from click.testing import CliRunner
from pika.exceptions import AMQPConnectionError, AMQPError, StreamLostError

from exchange_radar.consumer import main


@pytest.mark.parametrize("failure", [None, AMQPConnectionError("offline"), StreamLostError("lost"), ValueError("bad")])
def test_consumer_shares_session_and_closes_resources_on_reconnect_and_exit(monkeypatch, failure):
    channel = Mock()
    channel.start_consuming.side_effect = KeyboardInterrupt()
    connection = Mock(is_open=True)
    connection.channel.return_value = channel
    factory = Mock(side_effect=([failure] if failure is not None else []) + [connection])
    sessions = [Mock(), Mock()]
    session_factory = Mock(side_effect=sessions)
    monkeypatch.setattr(main.pika, "BlockingConnection", factory)
    monkeypatch.setattr(main.requests, "Session", session_factory)
    monkeypatch.setattr(main, "sleep", Mock())
    result = CliRunner().invoke(main.main)
    assert result.exit_code == 0, result.exception
    used = 2 if failure is not None else 1
    assert session_factory.call_count == used
    for session in sessions[:used]:
        session.close.assert_called_once()
    callbacks = [call.kwargs["on_message_callback"].__self__ for call in channel.basic_consume.call_args_list]
    assert len(callbacks) == 4
    assert all(callback.session is sessions[used - 1] for callback in callbacks)
    channel.stop_consuming.assert_called_once()
    connection.close.assert_called_once()


def test_connection_close_error_does_not_prevent_clean_exit(monkeypatch, caplog):
    channel = Mock()
    channel.start_consuming.side_effect = KeyboardInterrupt()
    connection = Mock(is_open=True)
    connection.channel.return_value = channel
    connection.close.side_effect = AMQPError("already closed")
    monkeypatch.setattr(main.pika, "BlockingConnection", Mock(return_value=connection))
    monkeypatch.setattr(main.requests, "Session", Mock())
    monkeypatch.setattr(main, "sleep", Mock())
    result = CliRunner().invoke(main.main)
    assert result.exit_code == 0
    assert "Error closing consumer connection" in caplog.text
