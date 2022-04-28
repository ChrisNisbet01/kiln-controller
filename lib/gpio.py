from enum import Enum, auto

from lib.gpio_base import GPIOBase
from lib.piface_gpio import PiFaceGPIO
from lib.rpi_gpio import PiGPIO


class GPIOType(Enum):
    Pi = auto()
    PiFace = auto()


def get_gpio(gpio_type: str) -> GPIOBase:
    gpio_types = {"piface": PiFaceGPIO, "pi": PiGPIO}
    return gpio_types[gpio_type]()
