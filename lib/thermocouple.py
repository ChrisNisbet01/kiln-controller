import logging
from typing import Protocol

from lib.config_from_yaml import ConfigThermocouple
from lib.gpio import GPIOBase
from lib.max31856 import MAX31856


log = logging.getLogger("thermocouple")


class Thermocouple(Protocol):
    name: str
    noConnection: bool
    shortToGround: bool
    shortToVCC: bool
    unknownError: bool

    def get(self) -> float:
        ...


MAX31856Type = {
    "MAX31856_B_TYPE": MAX31856.MAX31856_B_TYPE,  # Read B Type Thermocouple
    "MAX31856_E_TYPE": MAX31856.MAX31856_E_TYPE,  # Read E Type Thermocouple
    "MAX31856_J_TYPE": MAX31856.MAX31856_J_TYPE,  # Read J Type Thermocouple
    "MAX31856_K_TYPE": MAX31856.MAX31856_K_TYPE,  # Read K Type Thermocouple
    "MAX31856_N_TYPE": MAX31856.MAX31856_N_TYPE,  # Read N Type Thermocouple
    "MAX31856_R_TYPE": MAX31856.MAX31856_R_TYPE,  # Read R Type Thermocouple
    "MAX31856_S_TYPE": MAX31856.MAX31856_S_TYPE,  # Read S Type Thermocouple
    "MAX31856_T_TYPE": MAX31856.MAX31856_T_TYPE,  # Read T Type Thermocouple
}

def ThermocoupleCreate(
        cfg: ConfigThermocouple,
        temp_sensor_gpio: GPIOBase,
        temp_scale: str
):
    if cfg.type == "MAX31855":
        from lib.max31855 import MAX31855

        log.info(f"init MAX31855 - SPI type: {cfg.spi_type}")
        if cfg.spi_type == "PI_HW_SPI":
            from lib.max31855_spi_pi_hw import MAX31855SPIPiHW

            thermocouple_spi = MAX31855SPIPiHW(bus=0, device=0)
        elif cfg.spi_type == "BITBANG_SPI":
            from lib.max31855_spi_bit_bang import MAX31855SPIBitBang

            thermocouple_spi = MAX31855SPIBitBang(
                gpio=temp_sensor_gpio,
                cs_pin=cfg.gpio.sensor_cs,
                clock_pin=cfg.gpio.sensor_clock,
                data_pin=cfg.gpio.sensor_data)
        else:
            raise ValueError(f"Unknown Thermcouple SPI type: {cfg.spi_type}. "
                             f"Supported values are: BITBANG_SPI, PI_HW_SPI")
        thermocouple = MAX31855(spi=thermocouple_spi, units=temp_scale)
    elif cfg.type == "MAX31856":
        from lib.max31856 import MAX31856

        log.info("init MAX31856")
        software_spi = \
            {
                'cs': cfg.gpio.sensor_cs,
                'clk': cfg.gpio.sensor_clock,
                'do': cfg.gpio.sensor_data,
                'di': cfg.gpio.sensor_di
            }
        thermocouple = MAX31856(
            temp_sensor_gpio,
            tc_type=MAX31856Type[cfg.MAX31856_TYPE],
            software_spi=software_spi,
            units=temp_scale,
            ac_freq_50hz=cfg.ac_freq_50hz,
        )
    else:
        print(f"Unsupported thermocouple type: {cfg.type}")
        thermocouple = None

    return thermocouple
