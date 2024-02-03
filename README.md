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

    $ docker-compose -f local.yml up --build -d

#### Production

    $ docker-compose -f production.yml up --build -d

Scale the consumer service horizontally with 2 instances:

    $ docker-compose -f production.yml up --build --scale consumer=2

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
