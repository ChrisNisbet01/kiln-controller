import logging


log = logging.getLogger(__name__)


class PiGPIO:
    def __init__(self) -> None:
        try:
            import RPi.GPIO as GPIO
            self.GPIO = GPIO
        except ModuleNotFoundError:
            msg = "Could not initialize GPIOs, oven operation will only be simulated!"
            log.warning(msg)
            self.GPIO = None
        self._init_module()

    def _init_module(self) -> None:
        if not self.GPIO:
            return
        self.GPIO.setmode(self.GPIO.BCM)
        self.GPIO.setwarnings(False)

    def setup_pin(self, pin: int, output: bool) -> None:
        if not self.GPIO:
            return
        dir_ = self.GPIO.OUT if output else self.GPIO.IN
        self.GPIO.setup(pin, dir_)

    def set_pin(self, pin: int, set_on: bool) -> None:
        if not self.GPIO:
            return
        state = self.GPIO.HIGH if set_on else self.GPIO.LOW
        self.GPIO.output(pin, state)

    def get_pin(self, pin: int) -> bool:
        if not self.GPIO:
            return False
        return self.GPIO.input(pin)
