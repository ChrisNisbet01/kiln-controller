from typing import Protocol


class Thermocouple(Protocol):
    name: str
    noConnection: bool
    shortToGround: bool
    shortToVCC: bool
    unknownError: bool

    def get(self) -> float:
        ...
