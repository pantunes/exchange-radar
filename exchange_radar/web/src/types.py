from collections import defaultdict


class ERdefaultdict(defaultdict):
    def __get__(self, coin, category):
        return super().__getitem__(f"{coin}-{category}")
