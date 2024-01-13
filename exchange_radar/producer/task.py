import asyncio
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Task:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    async def task(self, symbols: tuple[str, ...]):
        await asyncio.gather(*[self.process(s) for s in symbols])

    async def process(self, symbol_or_symbols: str | tuple):
        raise NotImplementedError("Task to be Processed")

    def start(self, symbols: tuple[str, ...]):
        logger.info("Starting Task...")
        try:
            self.loop.run_until_complete(self.task(symbols))
        except KeyboardInterrupt:
            logger.info("Task was interrupted...")
        finally:
            pass
