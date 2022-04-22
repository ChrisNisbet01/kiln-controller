import datetime
import json
import logging
from dataclasses import dataclass
from enum import Enum, auto
from queue import Queue
from threading import Thread
from typing import Optional, Any, Union
from lib.config_from_yaml import Config
from lib.oven_time import Time
from lib.gpio import GPIOBase
from lib.gpio_output import Output
from lib.pid import PID
from lib.temp_sensor import TempSensor, TempSensorSimulated
from lib.timer import OvenTimer


log: logging.Logger = logging.getLogger("Oven")


class Profile:
    def __init__(self, json_data: str) -> None:
        obj = json.loads(json_data)
        self.name = obj["name"]
        self.data = sorted(obj["data"])

    @classmethod
    def from_json(cls, profile: Any) -> "Profile":
        profile_json = json.dumps(profile)
        return cls(profile_json)

    def get_duration(self) -> float:
        return max([t for (t, x) in self.data])

    def _get_surrounding_points(self, time_) -> Optional[tuple]:
        if time_ > self.get_duration():
            return None, None

        prev_point = None
        next_point = None

        for i in range(len(self.data)):
            if time_ < self.data[i][0]:
                prev_point = self.data[i-1]
                next_point = self.data[i]
                break

        return prev_point, next_point

    def get_target_temperature(self, time_) -> float:
        if time_ > self.get_duration():
            return 0

        prev_point, next_point = self._get_surrounding_points(time_)
        if prev_point is None or next_point is None:
            return 0

        incl = float(next_point[1] - prev_point[1]) / float(next_point[0] - prev_point[0])
        temp = prev_point[1] + (time_ - prev_point[0]) * incl
        return temp


class OvenMessageCode(Enum):
    ABORT_RUN = auto()
    RUN_PROFILE = auto
    EXPIRED_TIMER = auto()
    GET_STATE = auto()


@dataclass(frozen=True)
class OvenMessage:
    code: OvenMessageCode
    data: Optional[Any] = None


@dataclass(frozen=True)
class ProfileData:
    profile: Profile
    start_at_minute: float


class OvenState(Enum):
    IDLE = auto()
    RUNNING = auto()


class Oven(Thread):
    """
        Parent oven class. this has all the common code
        for either a real or simulated oven
    """
    _heat: float = 0
    _load_percent: float = 0
    temp_sensor: TempSensor
    _start_time: datetime.datetime
    _speed: int = 1
    _are_catching_up: bool = False
    _catchup_start_time: datetime.datetime
    _total_catch_up_secs: float = 0
    _state: OvenState
    _profile: Optional[Profile] = None
    _runtime_secs: float = 0
    _total_time_secs: float = 0
    _start_at_secs: float = 0
    _target_temp: float
    _pid: PID
    _queue: Queue
    _timer: OvenTimer
    _cfg: Config

    def __init__(
            self,
            cfg: Config,
            temp_sensor: Union[TempSensor, TempSensorSimulated]) -> None:
        super().__init__()
        self._cfg = cfg
        self._queue = Queue()
        self._start_at_secs = 0
        self.temp_sensor = temp_sensor
        self.daemon = True
        self.time_step = self._cfg.sensor_time_wait
        self._timer = OvenTimer(self._timeout)
        self._start_time = Time.now()
        self._reset()

    def __enter__(self) -> "Oven":
        # start thread
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback) -> None:
        self._reset()

    def _send_message(self, code: OvenMessageCode, data: Any = None):
        self._queue.put(OvenMessage(code=code, data=data))

    def _timeout(self):
        self._send_message(OvenMessageCode.EXPIRED_TIMER)

    def _reset(self) -> None:
        self._timer.stop()
        self._state = OvenState.IDLE
        self._profile = None
        self._total_catch_up_secs = 0
        self._runtime_secs = 0
        self._total_time_secs = 0
        self._target_temp = 0
        self._heat = 0
        self._load_percent = 0
        self._pid = PID(self._cfg.pid)
        self._are_catching_up = False

    def run_profile(self, profile: Profile, start_at_minute: float = 0) -> None:
        data = ProfileData(profile=profile, start_at_minute=start_at_minute)
        self._send_message(OvenMessageCode.RUN_PROFILE, data)

    def _run_profile(self, profile: Profile, start_at_minute: float = 0) -> None:
        self._reset()
        temp_sensor_status = self.temp_sensor.status
        if temp_sensor_status.noConnection:
            log.info("Refusing to start profile - thermocouple not connected")
            return
        if temp_sensor_status.shortToGround:
            log.info("Refusing to start profile - thermocouple short to ground")
            return
        if temp_sensor_status.shortToVCC:
            log.info("Refusing to start profile - thermocouple short to VCC")
            return
        if temp_sensor_status.unknownError:
            log.info("Refusing to start profile - thermocouple unknown error")
            return

        log.info("Running schedule %s" % profile.name)
        self._profile = profile
        self._total_time_secs = profile.get_duration()
        Time.speed_set(self._speed)
        self._start_time = Time.now()
        self._start_at_secs = start_at_minute * 60
        self._state = OvenState.RUNNING

    def abort_run(self) -> None:
        self._send_message(OvenMessageCode.ABORT_RUN)

    def _catch_up_on(self):
        if not self._are_catching_up:
            self._are_catching_up = True
            self._catchup_start_time = Time.now()

    def _catch_up_off(self):
        if self._are_catching_up:
            self._are_catching_up = False
            catch_up_time = Time.now() - self._catchup_start_time
            self._total_catch_up_secs += catch_up_time.total_seconds()

    def kiln_must_catch_up(self) -> None:
        """
        Determine if the kiln temperature needs to catch up. If true, start
        timing how long the oven is in catch up mode, and stop timing once the
        oven has caught up. This catch up time is accumulated and subtracted
        from the profile's runtime.

        :return: True if the kiln is catching up, else False.
        """
        if not self._cfg.kiln_must_catch_up:
            self._catch_up_off()
            return

        temperature = self.temp_sensor.temperature

        is_too_cold = self._target_temp - temperature > self._cfg.kiln_must_catch_up_max_error
        if is_too_cold:
            log.info("too cold - kiln must catch up")
            self._catch_up_on()
            return

        is_too_hot = temperature - self._target_temp > self._cfg.kiln_must_catch_up_max_error
        if is_too_hot:
            log.info("too hot - kiln must catch up")
            self._catch_up_on()
            return

        self._catch_up_off()

    def update_runtime(self) -> None:
        if self._are_catching_up:
            return
        runtime_delta = Time.now() - self._start_time
        if runtime_delta.total_seconds() < 0:
            runtime_delta = datetime.timedelta(0)
        self._runtime_secs = self._start_at_secs + runtime_delta.total_seconds() - self._total_catch_up_secs

    def update_target_temp(self) -> None:
        self._target_temp = self._profile.get_target_temperature(self._runtime_secs) if self._profile else 0

    def reset_if_emergency(self) -> None:
        """reset if the temperature is way TOO HOT, or other critical errors detected"""
        should_reset = False
        temp_sensor_status = self.temp_sensor.status
        if temp_sensor_status.temperature >= self._cfg.emergency_shutoff_temp:
            log.info("emergency!!! temperature too high.")
            should_reset = True

        if temp_sensor_status.noConnection:
            log.info("emergency!!! lost connection to thermocouple.")
            should_reset = True

        if temp_sensor_status.unknownError:
            log.info("emergency!!! unknown thermocouple error.")
            should_reset = True

        if temp_sensor_status.bad_percent > 30:
            log.info("emergency!!! too many errors in a short period.")
            should_reset = True

        if should_reset and not self._cfg.ignore_emergencies:
            log.info("Shutting down")
            self._reset()

    def reset_if_schedule_ended(self) -> None:
        if self._runtime_secs > self._total_time_secs:
            log.info("Schedule ended, shutting down.")
            self._reset()

    @property
    def runtime_info(self) -> dict:
        """
        To be called by threads other than the Oven thread to get state info.
        Will _not_ work if called by the oven thread itself.

        :return: Oven state information.
        """
        q = Queue()
        self._send_message(OvenMessageCode.GET_STATE, q)
        state = q.get()
        return state

    @property
    def _total_runtime_secs(self):
        # Actually the total runtime since the start of the program or the start
        # of the last profile run.
        # Used when including the actual temperature on the graph plot.
        total_runtime_secs = (Time.now() - self._start_time).total_seconds()
        return total_runtime_secs

    @property
    def _runtime_info(self) -> dict:
        """
        Called by the Oven thread. Returns runtime info to be written
        back to a queue supplied by the calling thread in the runtime_info
        method.
        """

        state = {
            'runtime': self._runtime_secs,
            'total_runtime': self._total_runtime_secs,
            'start_time': self._start_time.timestamp(),
            'temperature': self.temp_sensor.temperature,
            'target': self._target_temp,
            'state': self._state.name.capitalize(),
            'heat': self._heat,
            'load_percent': self._load_percent,
            'totaltime': self._total_time_secs,
            'kwh_rate': self._cfg.kwh_rate,
            'currency_type': self._cfg.currency_type,
            'profile': self._profile.name if self._profile else None,
            'pidstats': self._pid.pidstats,
        }
        return state

    def oven_is_running(self) -> None:
        pass

    def heat_then_cool(self) -> None:
        pass

    def run(self) -> None:
        while True:
            msg: OvenMessage = self._queue.get()
            self._process_message(msg)

    def _process_message(self, msg: OvenMessage) -> None:
        if msg.code == OvenMessageCode.ABORT_RUN:
            self._reset()
        elif msg.code == OvenMessageCode.RUN_PROFILE:
            profile_data: ProfileData = msg.data
            self._run_profile(profile_data.profile, profile_data.start_at_minute)
            log.info("Starting")
            self._update_oven()
        elif msg.code == OvenMessageCode.EXPIRED_TIMER:
            log.debug("Expired timer")
            self._update_oven()
        elif msg.code == OvenMessageCode.GET_STATE:
            q: Queue = msg.data
            q.put(self._runtime_info)
        else:
            log.debug(f"Oven ignoring message code: {msg.code.name}")

    def _update_oven(self) -> None:
        if self._state == OvenState.RUNNING:
            self.oven_is_running()
            self.kiln_must_catch_up()
            self.update_runtime()
            self.update_target_temp()
            self.heat_then_cool()
            self.reset_if_emergency()
            self.reset_if_schedule_ended()
        elif self._state == OvenState.IDLE:
            self._update_idle_oven()

    def _update_idle_oven(self) -> None:
        pass


class SimulatedOven(Oven):
    Q_h: float
    p_ho: float
    p_env: float
    temp_sensor: TempSensorSimulated

    def __init__(self, cfg: Config, temp_sensor: TempSensorSimulated) -> None:
        sim_cfg = cfg.simulate
        self._speed = sim_cfg.speed
        Time.speed_set(self._speed)
        self.t_env = sim_cfg.t_env
        self.c_heat = sim_cfg.c_heat
        self.c_oven = sim_cfg.c_oven
        self.p_heat = sim_cfg.p_heat
        self.R_o_nocool = sim_cfg.R_o_nocool
        self.R_ho_noair = sim_cfg.R_ho_noair
        self.R_ho = self.R_ho_noair

        # set temps to the temp of the surrounding environment
        self.t = self.t_env  # deg C temp of oven
        self.t_h = self.t_env  # deg C temp of heating element

        super().__init__(cfg, temp_sensor)

    def __enter__(self) -> Oven:
        log.info("SimulatedOven started")
        return super().__enter__()

    def _reset(self) -> None:
        super()._reset()
        self._timer.start(self.time_step / self._speed)

    def heating_energy(self, pid) -> None:
        # using pid here simulates the element being on for
        # only part of the time_step
        self.Q_h = self.p_heat * self.time_step * pid

    def temp_changes(self) -> None:
        # temperature change of heat element by heating
        self.t_h += self.Q_h / self.c_heat

        # energy flux heat_el -> oven
        self.p_ho = (self.t_h - self.t) / self.R_ho

        # temperature change of oven and heating element
        self.t += self.p_ho * self.time_step / self.c_oven
        self.t_h -= self.p_ho * self.time_step / self.c_heat

        # temperature change of oven by cooling to environment
        self.p_env = (self.t - self.t_env) / self.R_o_nocool
        self.t -= self.p_env * self.time_step / self.c_oven
        self.temp_sensor.set_temperature(self.t)

    def _update_idle_oven(self) -> None:
        # Update the temperature sensor reading when in the idle state to
        # simulate a cooling oven.

        self.heating_energy(0)
        self.temp_changes()
        log.info(f"temp: {self.temp_sensor.temperature:.2f}")
        self._timer.start(self.time_step / self._speed)

    def heat_then_cool(self) -> None:
        pid = self._pid.compute(self._target_temp, self.temp_sensor.temperature)
        heat_on_secs = float(self.time_step * pid)
        heat_off_secs = self.time_step - heat_on_secs

        self.heating_energy(pid)
        self.temp_changes()

        # self._heat is for the front end to display if the heat is on
        self._heat = heat_on_secs if heat_on_secs > 0 else 0.0
        self._load_percent = round(pid * 100, 1)

        log.info(
            "simulation: -> %dW heater: %.0f -> %dW oven: %.0f -> %dW env" %
            (int(self.p_heat * pid),
             self.t_h,
             int(self.p_ho),
             self.t,
             int(self.p_env)
             )
        )

        time_left = self._total_time_secs - self._runtime_secs
        log.info("temp=%.2f, target=%.2f, pid=%.3f, heat_on=%.2f, "
                 "heat_off=%.2f, run_time=%d, total_runtime=%d, total_time=%d, time_left=%d"
                 % (self.temp_sensor.temperature,
                    self._target_temp,
                    pid,
                    heat_on_secs,
                    heat_off_secs,
                    self._runtime_secs,
                    self._total_runtime_secs,
                    self._total_time_secs,
                    time_left
                    )
                 )
        # This is a simulation so there's no need for separate heating/cooling
        # times.
        self._timer.start(self.time_step / self._speed)


class RealOven(Oven):
    output: Output
    _master_output: Output
    _heat_on_secs: float = 0

    def __init__(self, cfg: Config, gpio: GPIOBase, temp_sensor: TempSensor) -> None:
        self._master_output = Output(gpio, cfg.outputs.enable)
        self._master_output_set(False)
        self.output = Output(gpio, cfg.outputs.heat)
        super().__init__(cfg, temp_sensor)

    def _master_output_set(self, turn_on: bool) -> None:
        log_it = self._master_output.state is None or turn_on != self._master_output.state
        self._master_output.set(turn_on)
        if log_it:
            log.info(f"Master output is {'On' if self._master_output.state else 'Off'}")

    def oven_is_running(self) -> None:
        if not self._master_output.state:
            self._master_output_set(True)

    def _reset(self) -> None:
        super()._reset()
        self.output.set(False)
        self._master_output_set(False)

    def heat_then_cool(self) -> None:
        timer_interval = self.time_step  # Default to the full time step.
        was_heating = self.output.state
        was_100_percent_heating = False
        if was_heating:  # Is only true when in the RUNNING state.
            # Avoid turning the heating element off/on when the kiln is operating
            # at 100% capacity. Perform a new load calculation if operating at
            # 100% - the element will be turned off once the load
            # drops below 100%.
            was_100_percent_heating = (self.time_step - self._heat_on_secs) == 0
            if not was_100_percent_heating:
                # Turn the element off for the rest of the time step.
                self.output.set(False)
                timer_interval = self.time_step - self._heat_on_secs
        if not was_heating or was_100_percent_heating:
            # Time to calculate the next heating time
            pid = self._pid.compute(
                self._target_temp, self.temp_sensor.temperature)
            heat_on_secs = float(self.time_step * pid)

            # self.heat is for the front end to display if the heat is on
            self._heat = 1.0 if heat_on_secs > 0 else 0.0
            self._load_percent = round(pid * 100, 1)

            if heat_on_secs > 0:
                self.output.set(True)
                timer_interval = heat_on_secs
                self._heat_on_secs = heat_on_secs
            else:
                self.output.set(False)

            time_left = self._total_time_secs - self._runtime_secs
            log.info("temp=%.2f, target=%.2f, pid=%.3f, heat_on_secs=%.2f, "
                     "heat_off_secs=%.2f, run_time=%d, total_runtime=%d, total_time=%d, time_left=%d" %
                     (self.temp_sensor.temperature,
                      self._target_temp,
                      pid,
                      heat_on_secs,
                      self.time_step - heat_on_secs,
                      self._runtime_secs,
                      self._total_runtime_secs,
                      self._total_time_secs,
                      time_left
                      )
                     )

        self._timer.start(timer_interval)
