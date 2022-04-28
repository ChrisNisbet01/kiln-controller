from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol


@dataclass
class GPIOConfig:
    pin: int
    output: bool
    active_low: bool = False


class GPIOBase(Protocol):

    def setup_pin(self, pin_config: GPIOConfig) -> None:
        ...

    def set_pin(self, pin: int, set_on: bool) -> None:
        ...

    def get_pin(self, pin: int) -> bool:
        ...


class GPIOType(Enum):
    Pi = auto()
    PiFace = auto()
