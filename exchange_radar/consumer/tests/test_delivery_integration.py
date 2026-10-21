import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pika
import pytest
import requests

from exchange_radar.consumer.delivery import Callback
from exchange_radar.consumer.main import setup_channel
from exchange_radar.feed import MAX_FEED_BATCH_SIZE


@pytest.mark.parametrize("count", [7, 100])
def test_real_broker_retries_failed_batches_without_acknowledging_early(count):
    url = os.environ.get("TEST_AMQP_URL")
    if not url:
        pytest.skip("Set TEST_AMQP_URL to run real RabbitMQ integration tests")
    attempts, accepted, ports, acknowledged, connections, handlers, errors = [], [], [], [], [], [], []
    failed, complete = threading.Event(), threading.Event()

    class Endpoint(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self):
            messages = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            attempts.append(messages)
            ports.append(self.client_address[1])
            status = 503 if len(attempts) == 1 else 200
            if status == 200:
                accepted.extend(message["id"] for message in messages)
            body = json.dumps({"accepted": len(messages)}).encode()
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    class ObservedCallback(Callback):
        def flush(self):
            super().flush()
            if self.retrying:
                failed.set()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Endpoint)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.start()
    controller = pika.BlockingConnection(pika.URLParameters(url))
    control = controller.channel()
    queue = f"radar-delivery-test:{uuid.uuid4().hex}"
    control.queue_declare(queue=queue)
    for trade_id in range(count):
        control.basic_publish(exchange="", routing_key=queue, body=json.dumps({"trade_symbol": "BTC", "id": trade_id}))

    def consume():
        try:
            with requests.Session() as session:
                connection = pika.BlockingConnection(pika.URLParameters(url))
                connections.append(connection)
                channel = connection.channel()
                ack = channel.basic_ack

                def record_ack(**kwargs):
                    ack(**kwargs)
                    acknowledged.append(kwargs["delivery_tag"])
                    if len(acknowledged) == count:
                        complete.set()

                channel.basic_ack = record_ack
                callback = ObservedCallback(f"http://127.0.0.1:{server.server_port}/feed/{{coin}}", session)
                handlers.append(callback)
                setup_channel(channel, queue, callback.callback)
                channel.start_consuming()
                connection.close()
        except Exception as error:
            errors.append(error)
            complete.set()

    thread = threading.Thread(target=consume)
    thread.start()
    try:
        assert failed.wait(10)
        assert acknowledged == []
        assert len(handlers[0].pending) == min(count, MAX_FEED_BATCH_SIZE)
        assert complete.wait(10)
        assert not errors
        assert len(acknowledged) == count
        assert accepted == list(range(count))
        assert attempts[0] == attempts[1]
        assert all(1 <= len(batch) <= MAX_FEED_BATCH_SIZE for batch in attempts)
        assert len(set(ports)) == 1  # The failed request's connection is reused too.
        assert control.queue_declare(queue=queue, passive=True).method.message_count == 0
    finally:
        if connections and handlers:
            connections[0].add_callback_threadsafe(handlers[0].channel.stop_consuming)
        thread.join(10)
        control.queue_delete(queue=queue)
        controller.close()
        server.shutdown()
        server.server_close()
        server_thread.join(5)
    assert not thread.is_alive()
