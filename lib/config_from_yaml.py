from dataclasses import dataclass
from typing import Type

import yaml
from yaml.scanner import ScannerError


@dataclass(frozen=True)
class ConfigPID:
    kp: float
    ki: float
    kd: float


@dataclass(frozen=True)
class ConfigSimulate:
    t_env: float
    c_heat: float
    c_oven: float
    p_heat: float
    R_o_nocool: float
    R_o_cool: float
    R_ho_noair: float
    R_ho_air: float
    speed: int = 1


@dataclass(frozen=True)
class ConfigOutputs:
    enable: int
    heat: int
    type: str = "pi"
    active_low: bool = False


@dataclass(frozen=True)
class ConfigThermocoupleGPIO:
    sensor_cs: int
    sensor_clock: int
    sensor_data: int
    sensor_di: int


@dataclass(frozen=True)
class ConfigThermocouple:
    MAX31856_TYPE: str
    gpio: ConfigThermocoupleGPIO
    honour_short_errors: bool
    temperature_average_samples: float
    ac_freq_50hz: bool = False
    type: str = "MAX31855"
    spi_type: str = "BITBANG_SPI"
    offset: float = 0.0


@dataclass(frozen=True)
class Config:
    log_format: str
    kwh_rate: float
    currency_type: str
    sensor_time_wait: int
    emergency_shutoff_temp: int
    pid: ConfigPID
    outputs: ConfigOutputs
    thermocouple: ConfigThermocouple
    simulate: ConfigSimulate = None
    log_level: str = "info"
    listening_ip: str = "0.0.0.0"
    listening_port: int = 8081
    simulated: bool = False
    temp_scale: str = "c"
    time_scale_slope: str = "h"
    time_scale_profile: str = "m"
    ignore_emergencies: bool = False
    kiln_must_catch_up: bool = True
    pid_control_window: float = 10.0

def config_constructor(
        loader: yaml.SafeLoader,
        node: yaml.nodes.MappingNode
) -> Config:
    """Construct a Config config (common parameters)."""
    return Config(**loader.construct_mapping(node))


def outputs_constructor(
        loader: yaml.SafeLoader,
        node: yaml.nodes.MappingNode
) -> ConfigOutputs:
    """Construct Outputs config (heater elements)."""
    return ConfigOutputs(**loader.construct_mapping(node))


def pid_constructor(
        loader: yaml.SafeLoader,
        node: yaml.nodes.MappingNode
) -> ConfigPID:
    """Construct PID config."""
    return ConfigPID(**loader.construct_mapping(node))


def simulate_constructor(
        loader: yaml.SafeLoader,
        node: yaml.nodes.MappingNode
) -> ConfigSimulate:
    """Construct Simulate config."""
    return ConfigSimulate(**loader.construct_mapping(node))


def thermocouple_gpio_constructor(
        loader: yaml.SafeLoader,
        node: yaml.nodes.MappingNode
) -> ConfigThermocoupleGPIO:
    """Construct thermocouple GPIO config."""
    return ConfigThermocoupleGPIO(**loader.construct_mapping(node))


def thermocouple_constructor(
        loader: yaml.SafeLoader,
        node: yaml.nodes.MappingNode
) -> ConfigThermocouple:
    """Construct thermocouple config."""
    return ConfigThermocouple(**loader.construct_mapping(node))


def get_loader() -> Type[yaml.SafeLoader]:
    """Add constructors to PyYAML loader."""
    loader = yaml.SafeLoader
    loader.add_constructor("!Config", config_constructor)
    loader.add_constructor("!Outputs", outputs_constructor)
    loader.add_constructor("!PID", pid_constructor)
    loader.add_constructor("!Simulate", simulate_constructor)
    loader.add_constructor("!ThermocoupleGPIO", thermocouple_gpio_constructor)
    loader.add_constructor("!Thermocouple", thermocouple_constructor)
    return loader


def load_config(config_file) -> Config:
    try:
        with open(config_file, "rb") as f:
            cfg = yaml.load(f, Loader=get_loader())
            return cfg
    except FileNotFoundError as e:
        raise ValueError(f"File not found: '{config_file}'") from e
    except ScannerError as e:
        raise ValueError("File format error") from e
