import time
from dataclasses import dataclass
from enum import Enum, auto
from queue import Queue
from threading import Thread
from typing import Optional, Any, Protocol

import config
from lib.log import log
from lib.thermocouple import Thermocouple
from lib.timer import OvenTimer


class TempSensorMessageCode(Enum):
    EXPIRED_TIMER = auto()
    GET_STATUS = auto()


@dataclass(frozen=True)
class TempSensorMessage:
    code: TempSensorMessageCode
    data: Optional[Any] = None


@dataclass(frozen=True)
class TempSensorStatus:
    temperature: float = 0
    bad_count: int = 0
    ok_count: int = 0
    bad_stamp: float = 0
    bad_percent: float = 0
    noConnection: bool = False
    shortToGround: bool = False
    shortToVCC: bool = False
    unknownError: bool = False


class TempSensor(Protocol):
    @property
    def name(self) -> str:
        raise NotImplementedError()

    @property
    def status(self) -> TempSensorStatus:
        raise NotImplementedError()

    @property
    def temperature(self) -> float:
        raise NotImplementedError()


class TempSensorSimulated:
    """not much here, just need to be able to set the temperature"""
    _temperature: float = 0

    @property
    def name(self) -> str:
        return "Simulated"

    def set_temperature(self, temperature: float) -> None:
        """
        Set the sensor temperature. Required for simulated Ovens only.

        :param temperature: The simulated temperature to assign.
        """
        self._temperature = temperature

    @property
    def status(self) -> TempSensorStatus:
        return TempSensorStatus(temperature=self._temperature)

    @property
    def temperature(self) -> float:
        return self._temperature


class TempSensorReal(Thread):
    """real temperature sensor thread that takes N measurements
       during the time_step"""
    thermocouple: Thermocouple
    _temperature: float = 0
    _bad_count: int = 0
    _ok_count: int = 0
    _bad_stamp: float = 0
    _bad_percent: float = 0
    _noConnection: bool = False
    _shortToGround: bool = False
    _shortToVCC: bool = False
    _unknownError: bool = False
    _sleep_secs: float
    _time_step: float
    _queue: Queue
    _timer: OvenTimer
    _thermocouple_offset: float

    def __init__(self, thermocouple: Thermocouple, thermocouple_offset: float = 0) -> None:
        super().__init__()
        self._thermocouple_offset = thermocouple_offset
        self._queue = Queue()
        self._timer = OvenTimer(self._timeout)
        self.daemon = True
        self._time_step = config.sensor_time_wait
        self._sleep_secs = self._time_step / float(config.temperature_average_samples)
        self.thermocouple = thermocouple
        self._timer.start(self._sleep_secs)
        self.start()

    @property
    def name(self) -> str:
        return self.thermocouple.name

    def _read_temperature(self, temps: list) -> None:
        # reset error counter if time is up
        if (time.time() - self._bad_stamp) > (self._time_step * 2):
            if self._bad_count + self._ok_count:
                self._bad_percent = (self._bad_count / (self._bad_count + self._ok_count)) * 100
            else:
                self._bad_percent = 0
            self._bad_count = 0
            self._ok_count = 0
            self._bad_stamp = time.time()

        temp = self.thermocouple.get()
        self._noConnection = self.thermocouple.noConnection
        self._shortToGround = self.thermocouple.shortToGround
        self._shortToVCC = self.thermocouple.shortToVCC
        self._unknownError = self.thermocouple.unknownError

        is_bad_value = self._noConnection | self._unknownError
        if config.honour_thermocouple_short_errors:
            is_bad_value |= self._shortToGround | self._shortToVCC

        if not is_bad_value:
            temps.append(temp)
            if len(temps) > config.temperature_average_samples:
                del temps[0]
            self._ok_count += 1

        else:
            log.error("Problem reading temp N/C:%s GND:%s VCC:%s ???:%s" %
                      (self._noConnection, self._shortToGround, self._shortToVCC, self._unknownError))
            self._bad_count += 1

        if len(temps):
            self._temperature = sum(temps) / len(temps)

    def _send_message(self, code: TempSensorMessageCode, data: Any = None) -> None:
        self._queue.put(TempSensorMessage(code=code, data=data))

    def _timeout(self) -> None:
        self._send_message(TempSensorMessageCode.EXPIRED_TIMER)

    @property
    def status(self) -> TempSensorStatus:
        q = Queue()
        self._send_message(TempSensorMessageCode.GET_STATUS, q)
        status: TempSensorStatus = q.get()
        return status

    @property
    def _status(self) -> TempSensorStatus:
        return TempSensorStatus(
            temperature=self._temperature + self._thermocouple_offset,
            bad_count=self._bad_count,
            bad_percent=self._bad_percent,
            bad_stamp=self._bad_stamp,
            ok_count=self._ok_count,
            noConnection=self._noConnection,
            shortToGround=self._shortToGround,
            shortToVCC=self._shortToVCC,
            unknownError=self._unknownError
        )

    @property
    def temperature(self) -> float:
        """
        Helper for the common case where just the temperature is required from
        the sensor status.
        """
        return self.status.temperature

    def run(self) -> None:
        """use a moving average of config.temperature_average_samples across the time_step"""
        temps = []
        while True:
            msg: TempSensorMessage = self._queue.get()
            if msg.code == TempSensorMessageCode.GET_STATUS:
                q: Queue = msg.data
                q.put(self._status)
            elif msg.code == TempSensorMessageCode.EXPIRED_TIMER:
                self._read_temperature(temps)
                self._timer.start(self._sleep_secs)
