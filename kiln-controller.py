#!/usr/bin/env python
import sys
import logging
from typing import Optional, Any

from geventwebsocket.websocket import WebSocket

from lib.oven import SimulatedOven, RealOven, Oven, Profile
from lib.ovenWatcher import OvenWatcher
from lib.rpi_gpio import PiGPIO
from lib.temp_sensor import TempSensorSimulated, TempSensorReal
from lib.piface_gpio import PiFaceGPIO
from lib.max31855 import MAX31855
from lib.max31856 import MAX31856
from web_server import create_web_server

try:
    sys.dont_write_bytecode = True
    import config
    sys.dont_write_bytecode = False
except ModuleNotFoundError:
    print("Could not import config file.")
    print("Copy config.py.EXAMPLE to config.py and adapt it for your setup.")
    exit(1)

logging.basicConfig(level=config.log_level, format=config.log_format)
log = logging.getLogger("kiln-controller")
log.info("Starting kiln controller")


def create_oven() -> Optional[Oven]:
    if config.simulate:
        log.info("Simulation mode")
        temp_sensor = TempSensorSimulated()
        oven_ = SimulatedOven(temp_sensor)
    else:
        log.info("Full operation mode")
        gpio_types = {config.PIFACE_GPIO: PiFaceGPIO, config.DIRECT_GPIO: PiGPIO}
        gpio_type = gpio_types[config.gpio_type]
        output_gpio = gpio_type()
        temp_sensor_gpio = PiGPIO()

        if config.max31855:
            log.info("init MAX31855")
            thermocouple = MAX31855(
                temp_sensor_gpio,
                config.gpio_sensor_cs,
                config.gpio_sensor_clock,
                config.gpio_sensor_data,
                config.temp_scale)
        elif config.max31856:
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
                tc_type=config.thermocouple_type,
                software_spi=software_spi,
                units=config.temp_scale,
                ac_freq_50hz=config.ac_freq_50hz,
            )
        else:
            print("No thermocouple specified. Select either max31855 or max31856 in config.py")
            return None

        # Temp debug use dummy sensor until real hardware arrives.
        # Note that temp sensor and heater outputs accessing the PiFace module on different threads
        # doesn't work - would need a lock. Doesn't really make sense to use PiFace GPIO to bitbang
        # thermocouple SPI anyway, so should use Pi GPIO for the thermocouple (faster if nothing else).
        # temp_sensor = TempSensorReal(thermocouple, config.thermocouple_offset)
        temp_sensor = TempSensorSimulated()
        oven_ = RealOven(output_gpio, temp_sensor)
    return oven_


class _OvenCallbacks:
    _oven: Oven
    _oven_watcher: OvenWatcher

    def __init__(self, oven_: Oven) -> None:
        self._oven = oven_
        self._oven_watcher = OvenWatcher(self._oven, config.sensor_time_wait)

    def run_profile(self, profile: Any, start_at_minute: float = 0) -> None:
        profile = Profile.from_json(profile)
        self._oven.run_profile(profile, start_at_minute=start_at_minute)
        self._oven_watcher.record(profile)

    def abort_run(self, ) -> None:
        self._oven.abort_run()

    def add_observer(self, wsock: WebSocket) -> None:
        self._oven_watcher.add_observer(wsock)


def main() -> None:
    with create_oven() as oven:
        callbacks = _OvenCallbacks(oven)
        web_server = create_web_server(config.listening_ip, config.listening_port, log, callbacks)
        web_server.serve_forever()


if __name__ == "__main__":
    try:
        main()
    finally:
        pass
