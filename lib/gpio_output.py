"""
Output module.
Defines the Output class used by the oven to drive the heating element outputs.
"""
from typing import Optional
from lib.gpio import GPIOBase
from lib.gpio_base import GPIOConfig


class Output:
    """
    Allows for driving a GPIO pin.
    """
    _gpio: GPIOBase
    _pin: int
    state: Optional[bool] = None

    def __init__(self, gpio: GPIOBase, pin: int, active_low: bool = False) -> None:
        self._gpio = gpio
        self._pin = pin
        self._gpio.setup_pin(GPIOConfig(pin=self._pin, output=True, active_low=active_low))

    def set(self, turn_on: bool) -> None:
        """
        Turn the output on or off

        :param turn_on: True if the output should turn on, else False to turn
        the output off.
        """
        self._gpio.set_pin(self._pin, turn_on)
        self.state = turn_on
