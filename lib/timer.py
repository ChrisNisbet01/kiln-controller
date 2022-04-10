from threading import Timer
from typing import Callable, Optional


class OvenTimer:
    _callback: Callable
    _timer: Optional[Timer] = None

    def __init__(self, callback: Callable):
        self._callback = callback

    def start(self, interval: float):
        if self._timer:
            self._timer.cancel()
        self._timer = Timer(interval, self._callback)
        self._timer.start()

    def stop(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None