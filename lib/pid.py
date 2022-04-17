import time
from dataclasses import dataclass

import config
from lib.oven_time import Time
from lib.log import log


@dataclass(frozen=True)
class PIDParams:
    kp: int = 1
    ki: int = 1
    kd: int = 1


class PID:

    def __init__(self, params: PIDParams) -> None:
        self.ki = params.ki
        self.kp = params.kp
        self.kd = params.kd
        self.lastNow = Time.now()
        self.iterm = 0
        self.last_err = 0
        self.pidstats = {}

    # FIX - this was using a really small window where the PID control
    # takes effect from -1 to 1. I changed this to various numbers and
    # settled on -50 to 50 and then divide by 50 at the end. This results
    # in a larger PID control window and much more accurate control...
    # instead of what used to be binary on/off control.
    def compute(self, setpoint, ispoint) -> float:
        now = Time.now()
        time_delta_secs = (now - self.lastNow).total_seconds()
        self.lastNow = now

        window_size = 100

        error = float(setpoint - ispoint)

        if self.ki > 0:
            if config.stop_integral_windup:
                if abs(self.kp * error) < window_size:
                    self.iterm += (error * time_delta_secs * (1 / self.ki))
            else:
                self.iterm += (error * time_delta_secs * (1 / self.ki))

        d_err = (error - self.last_err) / time_delta_secs
        output = self.kp * error + self.iterm + self.kd * d_err
        out4logs = output
        output = sorted([-1 * window_size, output, window_size])[1]
        self.last_err = error

        if output < 0:
            output = 0

        output = float(output / window_size)

        self.pidstats = {
            'time': time.mktime(now.timetuple()),
            'time_delta_secs': time_delta_secs,
            'setpoint': setpoint,
            'ispoint': ispoint,
            'err': error,
            'errDelta': d_err,
            'p': self.kp * error,
            'i': self.iterm,
            'd': self.kd * d_err,
            'kp': self.kp,
            'ki': self.ki,
            'kd': self.kd,
            'pid': out4logs,
            'out': output,
        }

        if out4logs > 0:
            log.info("pid actuals pid=%0.2f p=%0.2f i=%0.2f d=%0.2f" %
                     (
                         out4logs,
                         self.kp * error,
                         self.iterm,
                         self.kd * d_err
                     )
                     )

        return output
