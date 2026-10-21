# exchange-radar: Real-time Crypto Exchange Trades Monitor

[![Version][version-svg]][package-url]
[![License][license-image]][license-url]
[![Build Status][ci-svg]][ci-url]

Welcome to Exchange Radar, your gateway to real-time trade data from major cryptocurrency exchanges.

### Supported Exchanges
Exchange Radar currently supports the following top exchanges by reputation and trading volume:
- Binance
- Coinbase
- Kraken
- KuCoin
- OKX
- Bybit
- Bitstamp
- MEXC
- HTX

### Build & Run
Get started effortlessly:

#### Locally

    # Start all services (all crypto-exchange producers, consumer and web services)
    $ docker compose -f local.yml up --build -d

    # Start crypto-exchange OKX producer, consumer and web services
    $ docker compose -f local.yml up --build consumer producer-okx

#### Production

    # Start all services
    $ docker compose -f production.yml up --build -d

    # Scale the consumer service horizontally with 2 instances
    $ docker compose -f production.yml up --build --scale consumer=2

### Binance ingestion

Each Binance socket has a 5,000-message library buffer to absorb network bursts.
The default 100-message buffer can overflow before the application reader gets a
turn, even when processing is keeping up. Socket readers then put trades into a
bounded 5,000-trade shared processing queue. A single worker
updates Redis statistics in batches of up to 50 trades, flushing partial batches
after 20 ms. Every trade keeps its own cumulative statistics and existing alert
routing. Other exchange producers continue using their existing processing path.

A batch uses one atomic Redis script call instead of four network round trips per
trade. The worker retains a failed batch for retry before processing later trades;
trade IDs prevent repeated statistics updates, and the latest batch response is
cached for one hour to recover a lost Redis reply. Socket errors retain the capped
60-second reconnect backoff. Buffered trades remain in memory: process restarts or
long outages can still lose trades, and interrupted RabbitMQ publications can
produce duplicate deliveries.

A throughput log appears once per minute while trades are being processed, with
received/processed counts, pending queue depth, and the age of the completed batch.
A queue that keeps growing indicates the producer is still falling behind. Adding
consumers helps only when the downstream RabbitMQ queues are backing up.

The socket burst regression tests use the actual Binance library against a local
WebSocket server; no Binance API access is needed.

The Redis integration tests are opt-in. Set `TEST_REDIS_URL` to a reachable test
Redis instance when running pytest. Tests use unique key prefixes and remove only
their own keys.

### Consumer delivery

Producers send trades to the existing RabbitMQ queues over AMQP. Each consumer
collects up to 50 deliveries per queue, or waits up to 20 ms for a partial batch,
and forwards the batch over a reused HTTP connection. All four feed categories
use their existing endpoints with `_batch` in place of the coin, for example
`POST /api/feed/_batch` and `POST /api/feed/_batch/whales`.

The web service processes each trade in batch order, using its own `trade_symbol`
for browser delivery and the existing persistence rules. Single-trade requests
remain supported. Batch responses include `accepted`, the number of processed
trades; consumers acknowledge messages only after receiving the complete count.
An older web service cannot confirm this receipt, so new consumers retain their
messages until the web service is updated.

Prefetch bounds each consumer's unacknowledged deliveries to 50 per queue. Failed
HTTP batches are retained and retried with a 1–10 second backoff while AMQP
heartbeats continue. A closed broker connection requeues unacknowledged deliveries.
Delivery is at least once: a lost HTTP response or AMQP acknowledgement after
processing can cause duplicate browser deliveries or saved feed entries. Multiple
consumers do not provide global ordering across batches.

Set `TEST_AMQP_URL` to a test broker to run the optional transport integration
tests. They create uniquely named queues and remove only their own queues.

Consumers log delivered-message and HTTP-request counts once per minute while
active. Existing queued trades are retained during deployment. Build both images,
stop the old consumers before replacing the web service, then start two updated
consumers:

```bash
git pull &&
docker-compose -f production.yml build web consumer &&
docker-compose -f production.yml stop consumer &&
docker-compose -f production.yml up -d --no-deps web &&
docker-compose -f production.yml up -d --no-deps --scale consumer=2 consumer
```

### OAS 3
OpenAPI Specification: http://127.0.0.1:9000/api/schema.yaml

### Run Test Cases & Code Coverage

#### Tests

    $ make tests

#### Code Coverage

    $ make coverage

### Run Benchmarks

    $ make benchmark

Example of the benchmark output can be seen [here](benchmarks/results.out).

### UI
Explore real-time trade information effortlessly:
- Visit http://127.0.0.1:9000/BTC to access real-time BTC trades.
- To track BTC whales' transactions, navigate to http://127.0.0.1:9000/BTC/whales.
- For BTC dolphins' transactions, use http://127.0.0.1:9000/BTC/dolphins.
- To monitor BTC octopuses' transactions, head to http://127.0.0.1:9000/BTC/octopuses.

Feel free to replace BTC with any other supported coin across the exchanges.

### Hardware Requirements
Exchange Radar operates efficiently without requiring extensive resources. In fact, all services run seamlessly on a single Raspberry Pi 4.

<!-- Links -->

<!-- badges -->
[version-svg]: https://img.shields.io/pypi/v/exchange-radar?style=flat-square
[package-url]: https://pypi.org/project/exchange-radar/
[ci-svg]: https://github.com/pantunes/exchange-radar/actions/workflows/ci-cd.yml/badge.svg
[ci-url]: https://github.com/pantunes/exchange-radar/actions/workflows/ci-cd.yml
[license-image]: https://shields.io/badge/license-GNU%20General%20Public%20License%20v3.0-green
[license-url]: LICENSE
