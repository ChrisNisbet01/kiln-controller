#!/usr/bin/env python

import os
import sys
import csv
import time
import argparse

from lib.config_from_yaml import Config, load_config
from lib.gpio import get_gpio
from lib.rpi_gpio import PiGPIO
from lib.temp_sensor import TempSensorSimulated, TempSensorReal
from lib.thermocouple import ThermocoupleCreate

cfg: Config


def recordprofile(csvfile, targettemp) -> bool:

    script_dir = os.path.dirname(os.path.realpath(__file__))
    sys.path.insert(0, script_dir + '/lib/')

    from lib.oven import RealOven, SimulatedOven

    # open the file to log data to
    f = open(csvfile, 'w')
    csvout = csv.writer(f)
    csvout.writerow(['time', 'temperature'])

    # construct the oven
    if cfg.simulated:
        temp_sensor = TempSensorSimulated()
        oven = SimulatedOven(cfg, temp_sensor)
    else:
        output_gpio = get_gpio(cfg.outputs.type)
        temp_sensor_gpio = PiGPIO()

        thermocouple = ThermocoupleCreate(
            cfg=cfg.thermocouple,
            temp_sensor_gpio=temp_sensor_gpio,
            temp_scale=cfg.temp_scale)
        if not thermocouple:
            return False

        temp_sensor = TempSensorReal(cfg, thermocouple, cfg.thermocouple.offset)
        oven = RealOven(cfg, output_gpio, temp_sensor)

    # Main loop:
    #
    # * heat the oven to the target temperature at maximum burn.
    # * when we reach it turn the heating off completely.
    # * wait for it to decay back to the target again.
    # * quit
    #
    # We record the temperature every second
    try:
        stage = 'heating'
        if not cfg.simulated:
            oven.output.set(True)

        while True:
            temp = oven.temp_sensor.temperature

            csvout.writerow([time.time(), temp])
            f.flush()

            if stage == 'heating':
                if temp >= targettemp:
                    if not cfg.simulated:
                        oven.output.set(False)
                    stage = 'cooling'

            elif stage == 'cooling':
                if temp < targettemp:
                    break

            print("stage = %s, actual = %s, target = %s" % (stage, temp, targettemp))
            time.sleep(1)

        f.close()

    finally:
        # ensure we always shut the oven down!
        if not cfg.simulated:
            oven.output.set(False)
    return True


def line(a, b, x):
    return a * x + b


def invline(a, b, y):
    return (y - b) / a


def plot(xdata, ydata,
         tangent_min, tangent_max, tangent_slope, tangent_offset,
         lower_crossing_x, upper_crossing_x):
    from matplotlib import pyplot

    minx = min(xdata)
    maxx = max(xdata)
    miny = min(ydata)
    maxy = max(ydata)

    pyplot.scatter(xdata, ydata)

    pyplot.plot([minx, maxx], [miny, miny], '--', color='purple')
    pyplot.plot([minx, maxx], [maxy, maxy], '--', color='purple')

    pyplot.plot(tangent_min[0], tangent_min[1], 'v', color='red')
    pyplot.plot(tangent_max[0], tangent_max[1], 'v', color='red')
    pyplot.plot([minx, maxx],
                [line(tangent_slope, tangent_offset, minx), line(tangent_slope, tangent_offset, maxx)],
                '--',
                color='red')

    pyplot.plot([lower_crossing_x, lower_crossing_x], [miny, maxy], '--', color='black')
    pyplot.plot([upper_crossing_x, upper_crossing_x], [miny, maxy], '--', color='black')

    pyplot.show()


def calculate(filename, tangentdivisor, showplot):
    # parse the csv file
    xdata = []
    ydata = []
    filemintime = None
    with open(filename) as f:
        for row in csv.DictReader(f):
            try:
                time_ = float(row['time'])
                temp = float(row['temperature'])
                if filemintime is None:
                    filemintime = time_

                xdata.append(time_ - filemintime)
                ydata.append(temp)
            except ValueError:
                continue  # just ignore bad values!

    # gather points for tangent line
    miny = min(ydata)
    maxy = max(ydata)
    midy = (maxy + miny) / 2
    yoffset = int((maxy - miny) / tangentdivisor)
    tangent_min = tangent_max = None
    for i in range(0, len(xdata)):
        rowx = xdata[i]
        rowy = ydata[i]

        if rowy >= (midy - yoffset) and tangent_min is None:
            tangent_min = (rowx, rowy)
        elif rowy >= (midy + yoffset) and tangent_max is None:
            tangent_max = (rowx, rowy)

    # calculate tangent line to the main temperature curve
    tangent_slope = (tangent_max[1] - tangent_min[1]) / (tangent_max[0] - tangent_min[0])
    tangent_offset = tangent_min[1] - line(tangent_slope, 0, tangent_min[0])

    # determine the point at which the tangent line crosses the min/max temperaturess
    lower_crossing_x = invline(tangent_slope, tangent_offset, miny)
    upper_crossing_x = invline(tangent_slope, tangent_offset, maxy)

    # compute parameters
    L = lower_crossing_x - min(xdata)
    T = upper_crossing_x - lower_crossing_x

    # Magic Ziegler-Nicols constants ahead!
    Kp = 1.2 * (T / L)
    Ti = 2 * L
    Td = 0.5 * L
    Ki = Kp / Ti
    Kd = Kp * Td

    # output to the user
    print("pid_kp = %s" % Kp)
    print("pid_ki = %s" % (1 / Ki))
    print("pid_kd = %s" % Kd)

    if showplot:
        plot(xdata, ydata,
             tangent_min, tangent_max, tangent_slope, tangent_offset,
             lower_crossing_x, upper_crossing_x)


def main():
    parser = argparse.ArgumentParser(description='Kiln tuner')
    parser.add_argument("--config-file", nargs="?", dest="config_file", required=True, help="config file (yaml format)")
    subparsers = parser.add_subparsers()
    parser.set_defaults(mode='')

    parser_profile = subparsers.add_parser('recordprofile', help='Record kiln temperature profile')
    parser_profile.add_argument('csvfile', type=str, help="The CSV file to write to.")
    parser_profile.add_argument(
        '--targettemp',
        type=int,
        default=400,
        help="The target temperature to drive the kiln to (default 400).")
    parser_profile.set_defaults(mode='recordprofile')

    parser_zn = subparsers.add_parser('zn', help='Calculate Ziegler-Nicols parameters')
    parser_zn.add_argument(
        'csvfile',
        type=str,
        help="The CSV file to read from. Must contain two columns called time "
             "(time in seconds) and temperature (observed temperature)")
    parser_zn.add_argument(
        '--showplot',
        action='store_true',
        help="If set, also plot results (requires pyplot to be pip installed)")
    parser_zn.add_argument(
        '--tangentdivisor',
        type=float,
        default=8,
        help="Adjust the tangent calculation to fit better. "
             "Must be >= 2 (default 8).")
    parser_zn.set_defaults(mode='zn')

    args = parser.parse_args()
    global cfg
    cfg = load_config(args.config_file)

    if args.mode == 'recordprofile':
        if not recordprofile(args.csvfile, args.targettemp):
            exit(1)

    elif args.mode == 'zn':
        if args.tangentdivisor < 2:
            raise ValueError("tangentdivisor must be >= 2")

        calculate(args.csvfile, args.tangentdivisor, args.showplot)

    elif args.mode == '':
        parser.print_help()
        exit(1)

    else:
        raise NotImplementedError("Unknown mode %s" % args.mode)


if __name__ == "__main__":
    try:
        main()
    finally:
        pass
