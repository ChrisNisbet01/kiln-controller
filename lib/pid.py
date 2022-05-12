import logging
import time

from lib.config_from_yaml import ConfigPID
from lib.oven_time import Time


log = logging.getLogger("PID")


class PID:
    cfg: ConfigPID
    _control_enabled: bool = True

    def __init__(self, cfg: ConfigPID) -> None:
        self.cfg = cfg
        self.ki = cfg.ki
        self.kp = cfg.kp
        self.kd = cfg.kd
        self.lastNow = Time.now()
        self.iterm = 0
        self.last_err = 0
        self.pidstats = {}

    def enable_pid_control(self):
        self._control_enabled = True

    def disable_pid_control(self):
        self._control_enabled = False

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

        if self._control_enabled:
            # There seems little point in winding up the integral if the
            # P action alone will put the output above 100%.
            if self.ki > 0 and abs(self.kp * error) <= window_size:
                i_component = (error * time_delta_secs * (1 / self.ki))
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

        log.info("pid actuals pid=%0.2f p=%0.2f i=%0.2f d=%0.2f icomp=%0.2f error=%0.2f" %
                 (
                     out4logs,
                     self.kp * error,
                     self.iterm,
                     self.kd * d_err,
                     i_component,
                     error
                 )
                 )

        return output
