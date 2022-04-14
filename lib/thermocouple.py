from enum import Enum, auto
from typing import Protocol

import config
from lib.gpio import GPIOBase
from lib.log import log
from lib.max31856 import MAX31856


class Thermocouple(Protocol):
    name: str
    noConnection: bool
    shortToGround: bool
    shortToVCC: bool
    unknownError: bool

    def get(self) -> float:
        ...


# Better to register the supported types, but this will do for now.
class ThermocoupleType(Enum):
    MAX31855 = auto()
    MAX31856 = auto()


class MAX31856Type(Enum):
    MAX31856_B_TYPE = MAX31856.MAX31856_B_TYPE  # Read B Type Thermocouple
    MAX31856_E_TYPE = MAX31856.MAX31856_E_TYPE  # Read E Type Thermocouple
    MAX31856_J_TYPE = MAX31856.MAX31856_J_TYPE  # Read J Type Thermocouple
    MAX31856_K_TYPE = MAX31856.MAX31856_K_TYPE  # Read K Type Thermocouple
    MAX31856_N_TYPE = MAX31856.MAX31856_N_TYPE  # Read N Type Thermocouple
    MAX31856_R_TYPE = MAX31856.MAX31856_R_TYPE  # Read R Type Thermocouple
    MAX31856_S_TYPE = MAX31856.MAX31856_S_TYPE  # Read S Type Thermocouple
    MAX31856_T_TYPE = MAX31856.MAX31856_T_TYPE  # Read T Type Thermocouple


def ThermocoupleCreate(
        thermocouple_type: ThermocoupleType,
        temp_sensor_gpio: GPIOBase
):
    if thermocouple_type == ThermocoupleType.MAX31855:
        from lib.max31855 import MAX31855

        log.info("init MAX31855")
        thermocouple = MAX31855(
            temp_sensor_gpio,
            config.gpio_sensor_cs,
            config.gpio_sensor_clock,
            config.gpio_sensor_data,
            config.temp_scale)
    elif thermocouple_type == ThermocoupleType.MAX31856:
        from lib.max31856 import MAX31856

        log.info("init MAX31856")
        software_spi = \
            {
                'cs': config.gpio_sensor_cs,
                'clk': config.gpio_sensor_clock,
                'do': config.gpio_sensor_data,
                'di': config.gpio_sensor_di
            }
        thermocouple = MAX31856(
            temp_sensor_gpio,
            tc_type=config.MAX31856_TYPE,
            software_spi=software_spi,
            units=config.temp_scale,
            ac_freq_50hz=config.ac_freq_50hz,
        )
    else:
        print(f"Unsupported thermocouple type: {thermocouple_type.name}")
        thermocouple = None

    return thermocouple
