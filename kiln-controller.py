#!/usr/bin/env python
import argparse
import logging
from lib.config_from_yaml import Config, load_config
from typing import Optional, Any

from geventwebsocket.websocket import WebSocket

from lib.gpio import get_gpio
from lib.oven import SimulatedOven, RealOven, Oven, Profile
from lib.ovenWatcher import OvenWatcher
from lib.rpi_gpio import PiGPIO
from lib.temp_sensor import TempSensorSimulated, TempSensorReal
from lib.thermocouple import ThermocoupleCreate
from web_server import create_web_server


cfg: Config
log: logging.Logger


def create_oven() -> Optional[Oven]:
    if cfg.simulated:
        log.info("Simulation mode")
        temp_sensor = TempSensorSimulated()
        oven = SimulatedOven(cfg, temp_sensor)
    else:
        log.info("Full operation mode")
        output_gpio = get_gpio(cfg.outputs.type)
        temp_sensor_gpio = PiGPIO()

        thermocouple = ThermocoupleCreate(
            cfg=cfg.thermocouple,
            temp_sensor_gpio=temp_sensor_gpio,
            temp_scale=cfg.temp_scale)
        if not thermocouple:
            return None

        # Temp debug use dummy sensor until real hardware arrives.
        # Note that temp sensor and heater outputs accessing the PiFace module on different threads
        # doesn't work - would need a lock. Doesn't really make sense to use PiFace GPIO to bitbang
        # thermocouple SPI anyway, so should use Pi GPIO for the thermocouple (faster if nothing else).
        temp_sensor = TempSensorReal(cfg, thermocouple, cfg.thermocouple.offset)
        # temp_sensor = TempSensorSimulated()
        oven = RealOven(cfg, output_gpio, temp_sensor)
    return oven


class _OvenCallbacks:
    _oven: Oven
    _oven_watcher: OvenWatcher

    def __init__(self, oven_: Oven) -> None:
        self._oven = oven_
        self._oven_watcher = OvenWatcher(self._oven, cfg.sensor_time_wait)

    def run_profile(self, profile: Any, start_at_minute: float = 0) -> None:
        profile = Profile.from_json(profile)
        self._oven.run_profile(profile, start_at_minute=start_at_minute)
        self._oven_watcher.record(profile)

    def abort_run(self, ) -> None:
        self._oven.abort_run()

    def add_observer(self, wsock: WebSocket) -> None:
        self._oven_watcher.add_observer(wsock)


def parse_command_line() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kiln Controller",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--config-file", nargs="?", dest="config_file", required=True, help="config file (yaml format)")
    return parser.parse_args()


def setup_logger():
    levels = {
        "info": logging.INFO,
        "error": logging.ERROR,
        "debug": logging.DEBUG
    }
    if cfg.log_level not in levels:
        raise ValueError(f"Unsupported logging level: '{cfg.log_level}'. Legal values are: {list(levels.keys())}")
    logging.basicConfig(level=levels[cfg.log_level], format=cfg.log_format)


def main() -> None:
    global cfg
    global log

    args = parse_command_line()
    cfg = load_config(args.config_file)
    setup_logger()
    log = logging.getLogger("kiln-controller")
    log.info("Starting kiln controller")

    with create_oven() as oven:
        callbacks = _OvenCallbacks(oven)
        web_server = create_web_server(cfg, callbacks)
        web_server.serve_forever()


if __name__ == "__main__":
    try:
        main()
    finally:
        pass
