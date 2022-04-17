import time
from datetime import datetime as dt


class Time:
    _speed: int = 1
    _reference_time: float = time.time()

    @classmethod
    def speed_set(cls, speed: int):
        cls._speed = speed
        cls._reference_time = time.time()

    @classmethod
    def speed_get(cls):
        return cls._speed

    @classmethod
    def now(cls) -> dt:
        oven_time = cls._reference_time + cls._speed * (time.time() - cls._reference_time)
        return dt.fromtimestamp(oven_time)
