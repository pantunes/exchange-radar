# exchange-radar: Real-time Crypto Exchange Trades Monitor
Welcome to Exchange Radar, your gateway to real-time trade data from major cryptocurrency exchanges.

### Supported Exchanges
Exchange Radar currently supports the following top 4 exchanges by trading volume:
- Binance
- Coinbase
- Kraken
- Kucoin

### Build & Run
Get started effortlessly:

#### Locally

    $ docker-compose -f local.yml up --build -d

#### Production

    $ docker-compose -f production.yml up --build -d

Scale the consumer service horizontally with 2 instances:

    $ docker-compose -f production.yml up --build --scale consumer=2

### Accessing data
Explore real-time trade information effortlessly:
- Visit http://127.0.0.1:9000/BTC to access real-time BTC trades.
- To track BTC whales' transactions, navigate to http://127.0.0.1:9000/BTC/whales.
- For BTC dolphins' transactions, use http://127.0.0.1:9000/BTC/dolphins.
- To monitor BTC octopuses' transactions, head to http://127.0.0.1:9000/BTC/octopuses.

Feel free to replace BTC with any other supported coin across the exchanges.

### Hardware Requirements
Exchange Radar operates efficiently without requiring extensive resources. In fact, all services run seamlessly on a single Raspberry Pi 4.
