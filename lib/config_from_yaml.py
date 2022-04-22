import yaml
from yaml.scanner import ScannerError


class ConfigMap:
    def __init__(self, cfg: dict):
        self._cfg = cfg

    def __getattribute__(self, name: str):
        try:
            return super().__getattribute__(name)
        except AttributeError:
            return super().__getattribute__("_cfg")[name]


class ConfigPID(ConfigMap):
    kp: float
    ki: float
    kd: float
    stop_integral_windup: bool


class ConfigSimulate(ConfigMap):
    speed: int
    t_env: float
    c_heat: float
    c_oven: float
    p_heat: float
    R_o_nocool: float
    R_o_cool: float
    R_ho_noair: float
    R_ho_air: float


class ConfigOutputs(ConfigMap):
    type: str
    enable: int
    heat: int


class ConfigThermocoupleGPIO(ConfigMap):
    sensor_cs: int
    sensor_clock: int
    sensor_data: int
    sensor_di: int


class ConfigThermocouple(ConfigMap):
    type: str
    MAX31856_TYPE: str
    spi_type: str
    gpio: ConfigThermocoupleGPIO
    offset: float
    honour_short_errors: bool
    temperature_average_samples: float
    ac_freq_50hz: bool

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.gpio = ConfigThermocoupleGPIO(cfg["gpio"])


class Config(ConfigMap):
    log_level: str
    log_format: str
    listening_ip: str
    listening_port: int
    kwh_rate: float
    currency_type: str
    sensor_time_wait: int
    simulated: bool
    temp_scale: str
    time_scale_slope: str
    time_scale_profile: str
    emergency_shutoff_temp: int
    kiln_must_catch_up: bool
    kiln_must_catch_up_max_error: int
    ignore_emergencies: bool
    outputs: ConfigOutputs
    thermocouple: ConfigThermocouple
    pid: ConfigPID
    simulate: ConfigSimulate

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        if "outputs" in cfg:
            self.outputs = ConfigOutputs(cfg["outputs"])
        if "thermocouple" in cfg:
            self.thermocouple = ConfigThermocouple(cfg["thermocouple"])
        if "pid" in cfg:
            self.pid = ConfigPID(cfg["pid"])
        if "simulate" in cfg:
            self.simulate = ConfigSimulate(cfg["simulate"])
        return


def load_config(config_file) -> Config:
    try:
        with open(config_file, "r") as f:
            cfg = Config(yaml.safe_load(f))
            return cfg
    except FileNotFoundError as e:
        raise ValueError(f"File not found: '{config_file}'") from e
    except ScannerError as e:
        raise ValueError("File format error") from e
