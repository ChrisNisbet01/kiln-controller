import time
from datetime import datetime as dt


_speed: float = 1
_reference_time: float = time.time()


def set_speed(speed: float):
    global _speed
    global _reference_time

    _speed = speed
    _reference_time = time.time()

def now() -> dt:
    oven_time = _reference_time + _speed * (time.time() - _reference_time)
    return dt.fromtimestamp(oven_time)
