import importlib
import logging

import click

from exchange_radar.producer.settings.exchanges import EXCHANGES, EXCHANGES_LIST

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@click.command()
@click.argument("symbols", nargs=-1, required=True, type=str)
@click.option("--exchange", "-e", required=True, type=click.Choice(EXCHANGES_LIST))
def main(symbols: tuple, exchange: str):
    module_path = f"exchange_radar.producer.tasks.{exchange}"
    module = importlib.import_module(module_path)
    task = getattr(module, EXCHANGES[exchange])()

    logger.info(f"Exchange: {exchange}")
    logger.info(f"Symbols: {symbols}")

    task.start(symbols=symbols)

    logger.info("Task is over!")


if __name__ == "__main__":
    main()
