import logging

from tinydb import TinyDB

from exchange_radar.web.src.settings import base as settings

db = TinyDB(settings.DB_PATH)

logger = logging.getLogger(__name__)


class Db:
    @staticmethod
    def _get_table(cls_name: str, coin: str):
        name = f"{cls_name}-{coin}"
        return db.table(name=name)

    @staticmethod
    def read(cls_name: str, coin: str) -> list:
        table = Db._get_table(cls_name, coin)
        return table.all()

    @staticmethod
    def write(cls_name: str, coin: str, message: dict):
        if coin not in ("LTO",):
            if cls_name not in (
                "FeedWhales",
                "FeedDolphins",
            ):
                return

        table = Db._get_table(cls_name, coin)
        table.insert(message)

        if len(table) > settings.DB_TABLE_MAX_ROWS:
            table.remove(doc_ids=[table.all()[0].doc_id])
