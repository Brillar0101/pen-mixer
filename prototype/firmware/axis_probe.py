# axis_probe.py - Seeed XIAO nRF52840 Sense
#
# Shows which IMU axis moves for each pen gesture. Copy this onto CIRCUITPY
# as code.py (keep a backup of the real one), open the serial console, and
# move the pen one gesture at a time:
#
#     tilt  (lean forward/back)   -> accel X changes, tilt angle follows
#     twist (spin on long axis)   -> accel Y and Z trade places, roll follows
#     sway  (swing left/right)    -> gyro Z spikes, sway builds then leaks back
#
# If a gesture lands on the wrong column, the board is mounted differently
# than assumed: swap the axes in code.py's read_motion() or change SWAY_AXIS.
#
# Needs the same libraries as code.py on CIRCUITPY/lib:
#     adafruit_lsm6ds/  adafruit_bus_device/  adafruit_register/

import math
import time

import board
import busio
import digitalio

PRINT_HZ = 10  # slow enough to read in a serial console

imu_pwr = digitalio.DigitalInOut(board.IMU_PWR)
imu_pwr.direction = digitalio.Direction.OUTPUT
imu_pwr.value = True
time.sleep(0.1)

from adafruit_lsm6ds.lsm6ds3trc import LSM6DS3TRC

i2c = busio.I2C(board.IMU_SCL, board.IMU_SDA)
imu = LSM6DS3TRC(i2c)

# Same sway integrator as code.py, run at the print rate.
SWAY_AXIS = 2
SWAY_SCALE = 1.5
SWAY_LEAK = 0.97
sway = 0.0

period = 1.0 / PRINT_HZ

print("accel x      y      z  |  gyro x     y      z  |  tilt   roll   sway")

while True:
    ax, ay, az = imu.acceleration
    gx, gy, gz = imu.gyro

    tilt = math.degrees(math.atan2(ax, math.sqrt(ay * ay + az * az)))
    roll = math.degrees(math.atan2(ay, az))
    gyro = (gx, gy, gz)
    sway = sway * SWAY_LEAK + gyro[SWAY_AXIS] * period / SWAY_SCALE
    sway = max(-1.0, min(1.0, sway))

    print(
        "%6.2f %6.2f %6.2f  | %6.2f %6.2f %6.2f  | %6.1f %6.1f %6.3f"
        % (ax, ay, az, gx, gy, gz, tilt, roll, sway)
    )
    time.sleep(period)
