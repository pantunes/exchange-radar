from enum import Enum, unique


class BaseEnum(Enum):
    @classmethod
    def choices(cls):
        return [(key.name, key.value) for key in cls]


@unique
class Ranking(BaseEnum):
    WHALE = "Whale"
    DOLPHIN = "Dolphin"
    OCTOPUS = "Octopus"
