import logging
from typing import Dict

from lib.gpio_base import GPIOConfig

log = logging.getLogger(__name__)


class PiGPIO:
    pins: Dict

    def __init__(self) -> None:
        try:
            import RPi.GPIO as GPIO
            self.GPIO = GPIO
        except ModuleNotFoundError:
            msg = "Could not initialize GPIOs, oven operation will only be simulated!"
            log.warning(msg)
            self.GPIO = None
        self.pins = {}
        self._init_module()

    def _init_module(self) -> None:
        if not self.GPIO:
            return
        self.GPIO.setmode(self.GPIO.BCM)
        self.GPIO.setwarnings(False)

    def add_pin_config(self, pin_config: GPIOConfig):
        self.pins[pin_config.pin] = pin_config

    def setup_pin(self, pin_config: GPIOConfig) -> None:
        if not self.GPIO:
            return
        self.add_pin_config(pin_config)
        dir_ = self.GPIO.OUT if pin_config.output else self.GPIO.IN
        self.GPIO.setup(pin_config.pin, dir_)
        if dir_ == self.GPIO.OUT:
            # Turn the output off initially
            self.set_pin(pin_config.pin, False)

    def set_pin(self, pin: int, set_on: bool) -> None:
        if not self.GPIO:
            return
        if pin not in self.pins:
            return
        pin_config: GPIOConfig = self.pins[pin]
        state = self.GPIO.HIGH if set_on else self.GPIO.LOW
        state ^= pin_config.active_low
        self.GPIO.output(pin, state)

    def get_pin(self, pin: int) -> bool:
        if not self.GPIO:
            return False
        if pin not in self.pins:
            return False
        pin_config: GPIOConfig = self.pins[pin]
        return self.GPIO.input(pin) ^ pin_config.active_low
