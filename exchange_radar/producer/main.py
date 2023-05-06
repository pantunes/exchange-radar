import logging

import click

from exchange_radar.producer.settings.exchanges import EXCHANGES

logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


@click.command()
@click.argument("symbols", nargs=-1, required=True, type=str)
@click.option(
    "--exchange", "-e", required=True, type=click.Choice(list(EXCHANGES.keys()))
)
def main(symbols: tuple, exchange: str):
    task = EXCHANGES[exchange]()

    logger.info(f"Exchange: {exchange}")
    logger.info(f"Symbols: {symbols}")

    task.start(symbols=symbols)

    logger.info("Task is over!")


if __name__ == "__main__":
    main()
