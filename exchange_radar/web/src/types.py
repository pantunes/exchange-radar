from collections import defaultdict


class ERdefaultdict(defaultdict):
    def __get__(self, coin: str, category: str):
        return super().__getitem__(f"{coin}-{category}")
