import logging


log = logging.getLogger(__name__)


class PiFaceGPIO:
    def __init__(self) -> None:
        try:
            import pifacedigitalio as piface
        except ModuleNotFoundError:
            msg = "Could not initialize GPIOs, oven operation will only be simulated!"
            log.warning(msg)
            piface = None
        self.piface = piface
        self._init_module()

    def _init_module(self) -> None:
        if not self.piface:
            return
        self.piface.init()

    def setup_pin(self, pin: int, output: bool) -> None:
        # Nothing to do. Set all outputs off when first set up though.
        if not self.piface:
            return
        if output:
            self.piface.digital_write(pin, False)

    def set_pin(self, pin: int, state: bool) -> None:
        # Assumes that an output should be set.
        if not self.piface:
            return
        self.piface.digital_write(pin, state)

    def get_pin(self, pin: int) -> bool:
        # Assumes that pin refers to an input pin
        if not self.piface:
            return False
        return self.piface.digital_read(pin)
