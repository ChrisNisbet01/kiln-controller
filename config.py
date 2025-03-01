import logging

########################################################################
#
#   General options

log_level = logging.INFO
log_format = '%(asctime)s %(levelname)s %(name)s: %(message)s'

### Server
listening_ip = "0.0.0.0"
listening_port = 8081

### Cost Estimate
kwh_rate = 0.30  # Rate in currency_type to calculate cost to run job
currency_type = "$"   # Currency Symbol to show when calculating cost to run job

########################################################################
#
#   GPIO Setup (BCM SoC Numbering Schema)
#
#   Check the RasPi docs to see where these GPIOs are
#   connected on the P1 header for your board type/rev.
#   These were tested on a Pi B Rev2 but of course you
#   can use whichever GPIO you prefer/have available.

### Outputs
# gpio_type: Possible values are:
# "pi": regular Raspberry Pi GPIO
# "piface": "Piface GPIO hat"
gpio_type = "pi"

gpio_enable = 0  # Master enable contactor
gpio_heat = 1  # Switches zero-cross solid-state-relay

### Thermocouple Adapter selection:
MAX31856Type = "MAX31856Type.MAX31856_S_TYPE"

### Thermocouple Connection (using bitbang interfaces)
#gpio_sensor_cs = 2
#gpio_sensor_clock = 3
#gpio_sensor_data = 4
#gpio_sensor_di = 5
gpio_sensor_cs = 27
gpio_sensor_clock = 22
gpio_sensor_data = 17
gpio_sensor_di = 10  # only used with max31856

########################################################################
#
# duty cycle of the entire system in seconds
#
# Every N seconds a decision is made about switching the relay[s]
# on & off and for how long. The thermocouple is read
# temperature_average_samples times during and the average value is used.
sensor_time_wait = 2


########################################################################
#
#   PID parameters
#
# These parameters control kiln temperature change. You must tune them
# to work well with your specific kiln.
# Note that the integral pid_ki is
# inverted so that a smaller number means more integral action.
pid_kp = 25   # Proportional
pid_ki = 200  # Integral
pid_kd = 200  # Derivative

# The simulated oven has separate PID parameters.
# These settings work well with the simulated oven.
simulated_pid_kp = 10  # Proportional
simulated_pid_ki = 50  # Integral
simulated_pid_kd = 50  # Derivative

########################################################################
#
# Initial heating and Integral Windup
#
# During initial heating, if the temperature is constantly under the
# setpoint, large amounts of Integral can accumulate. This accumulation
# causes the kiln to run above the setpoint for potentially a long
# period of time. These settings allow integral accumulation only when
# the temperature is close to the setpoint. This applies only to the integral.
stop_integral_windup = True

########################################################################
#
#   Simulation parameters
simulate       = True
sim_speed      = 10       # The speed the simulator runs at (1 ~= realtime, >1 = faster)
sim_t_env      = 21.0     # deg C
sim_c_heat     = 100.0    # J/K  heat capacity of heat element
sim_c_oven     = 5000.0   # J/K  heat capacity of oven
sim_p_heat     = 10000.0  # W    heating power of oven
sim_R_o_nocool = 0.3      # K/W  thermal resistance oven -> environment
sim_R_o_cool   = 0.05     # K/W  " with cooling
sim_R_ho_noair = 0.1      # K/W  thermal resistance heat element -> oven
sim_R_ho_air   = 0.05     # K/W  " with internal air circulation


########################################################################
#
#   Time and Temperature parameters
#
# If you change the temp_scale, all settings in this file are assumed to
# be in that scale.

temp_scale          = "c"  # c = Celsius | f = Fahrenheit - Unit to display
time_scale_slope    = "h"  # s = Seconds | m = Minutes | h = Hours - Slope displayed in temp_scale per time_scale_slope
time_scale_profile  = "m"  # s = Seconds | m = Minutes | h = Hours - Enter and view target time in time_scale_profile

# emergency shutoff the profile if this temp is reached or exceeded.
# This just shuts off the profile. If your SSR is working, your kiln will
# naturally cool off. If your SSR has failed/shorted/closed circuit, this
# means your kiln receives full power until your house burns down.
# this should not replace you watching your kiln or use of a kiln-sitter
emergency_shutoff_temp = 2264  # cone 7

# If the kiln cannot heat or cool fast enough and is off by more than
# kiln_must_catch_up_max_error  the entire schedule is shifted until
# the desired temperature is reached. If your kiln cannot attain the
# wanted temperature, the schedule will run forever. This is often used
# for heating as fast as possible in a section of a kiln schedule/profile.
kiln_must_catch_up = True
kiln_must_catch_up_max_error = 5  # degrees

# thermocouple offset
# If you put your thermocouple in ice water, and it reads 36F, you can
# set this offset to -4 to compensate.  This probably means you have a
# cheap thermocouple.  Invest in a better thermocouple.
thermocouple_offset = 0.0

# some kilns/thermocouples start erroneously reporting "short"
# errors at higher temperatures due to plasma forming in the kiln.
# Set this to False to ignore these errors and assume the temperature
# reading was correct anyway
honour_thermocouple_short_errors = False

# number of samples of temperature to average.
# If you suffer from the high temperature kiln issue and have set
# honour_thermocouple_short_errors to False,
# you will likely need to increase this (eg I use 40)
temperature_average_samples = 40

# There are all kinds of emergencies that can happen including:
# - temperature is too high (emergency_shutoff_temp exceeded)
# - lost connection to thermocouple
# - unknown error with thermocouple
# - too many errors in a short period from thermocouple
# and some people just want to ignore all of that and just log the emergencies but do not quit
ignore_emergencies = False
