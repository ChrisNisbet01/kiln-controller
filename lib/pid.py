import logging
import time
from dataclasses import dataclass, asdict

from lib.config_from_yaml import ConfigPID
from lib.oven_time import Time


log = logging.getLogger("PID")


@dataclass(frozen=True)
class PIDStats:
    time: float = 0
    time_delta_secs: float = 0
    setpoint: float = 0
    ispoint: float = 0
    err: float = 0
    errDelta: float = 0
    p: float = 0
    i: float = 0
    d: float = 0
    kp: float = 0
    ki: float = 0
    kd: float = 0
    pid: float = 0
    out: float = 0

    @property
    def asdict(self):
        return asdict(self)


class PID:
    cfg: ConfigPID
    _control_enabled: bool = True
    pidstats: PIDStats

    def __init__(self, cfg: ConfigPID) -> None:
        self.cfg = cfg
        self.ki = cfg.ki
        self.kp = cfg.kp
        self.kd = cfg.kd
        self.lastNow = Time.now()
        self.iterm = 0
        self.last_err = 0
        self.pidstats = PIDStats()

    def enable_pid_control(self):
        self._control_enabled = True

    def disable_pid_control(self):
        self._control_enabled = False

    def compute(self, setpoint, ispoint) -> float:
        now = Time.now()
        time_delta_secs = (now - self.lastNow).total_seconds()
        self.lastNow = now

        window_size = 100

        error = float(setpoint - ispoint)

        if self._control_enabled:
            # There seems little point in winding up the integral if the
            # P action alone will put the output above 100%.
            if abs(self.kp * error) <= window_size:
                i_component = (error * time_delta_secs * self.ki)
            else:
                i_component = 0.0
            self.iterm += i_component
            d_err = (error - self.last_err) / time_delta_secs
            output = self.kp * error + self.iterm + self.kd * d_err
        else:
            # No integral action component until within the
            # control window. P action should be sufficient to
            # get temperature within the control window.
            i_component = 0.0
            self.iterm = i_component
            d_err = 0
            if error < 0:  # Too hot.
                log.info("kiln outside pid control window, max cooling")
                output = 0
            else:
                log.info("kiln outside pid control window, max heating")
                output = window_size
        self.last_err = error
        out4logs = output

        # Limit to window size. No cooling, so low limit is 0.
        output = sorted([0, output, window_size])[1]
        # Scale to 0 -> 1
        output = float(output / window_size)

        self.pidstats = PIDStats(
            time=time.mktime(now.timetuple()),
            time_delta_secs=time_delta_secs,
            setpoint=setpoint,
            ispoint=ispoint,
            err=error,
            errDelta=d_err,
            p=self.kp * error,
            i=self.iterm,
            d=self.kd * d_err,
            kp=self.kp,
            ki=self.ki,
            kd=self.kd,
            pid=out4logs,
            out=output,
        )

        return output
