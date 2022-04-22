from enum import Enum, auto
from typing import Protocol
from lib.piface_gpio import PiFaceGPIO
from lib.rpi_gpio import PiGPIO


class GPIOBase(Protocol):

    def setup_pin(self, pin: int, output: bool) -> None:
        ...

    def set_pin(self, pin: int, set_on: bool) -> None:
        ...

    def get_pin(self, pin: int) -> bool:
        ...


class GPIOType(Enum):
    Pi = auto()
    PiFace = auto()


def get_gpio(gpio_type: str) -> GPIOBase:
    gpio_types = {"piface": PiFaceGPIO, "pi": PiGPIO}
    return gpio_types[gpio_type]()
