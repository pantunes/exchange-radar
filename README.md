# exchange-radar
Get real-time trades from various crypto exchanges.

So far the following crypto exchanges are supported:
- Binance
- Coinbase
- Kraken
- Kucoin

Currently, these are the top 4 exchanges by highest volume.

### Build & Run
As simple as:

#### Locally

    $ docker-compose -f local.yml up --build -d

#### Production

    $ docker-compose -f production.yml up --build -d

Example of how to spin all services and scale the service `consumer` horizontally with 2 instances:

    $ docker-compose -f production.yml up --build --scale consumer=2

### Client
Access `http://127.0.0.1:9000/BTC` and voilá!

All BTC trades are displayed in real-time.

To check BTC whales transactions hit `http://127.0.0.1:9000/BTC/whales` \
To check BTC dolphins transactions hit `http://127.0.0.1:9000/BTC/dolphins` \
To check BTC octopuses transactions hit `http://127.0.0.1:9000/BTC/octopuses`

Use any other coin that the exchanges support - The coin `BTC` was used as an example.
