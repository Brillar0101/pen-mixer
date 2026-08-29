# code.py - Seeed XIAO nRF52840 Sense
#
# Reads the onboard LSM6DS3TR-C 6-axis IMU and streams motion over USB serial
# as "tilt,roll,energy" at ~250 Hz - the same frame format the RP2040 touch
# build uses, so the bridge, dashboard and Pd patches are unchanged.
#
# REQUIRES on CIRCUITPY/lib :
#     adafruit_lsm6ds/          (folder)
#     adafruit_bus_device/      (folder)
#     adafruit_register/        (folder)
# from the CircuitPython library bundle at circuitpython.org/libraries

import math
import time

import board
import busio
import digitalio

FRAME_HZ = 250
G = 9.80665

# The Sense's IMU sits on its own I2C bus and is unpowered at boot.
# Forgetting this line is the usual reason the sensor "isn't found".
imu_pwr = digitalio.DigitalInOut(board.IMU_PWR)
imu_pwr.direction = digitalio.Direction.OUTPUT
imu_pwr.value = True
time.sleep(0.1)

try:
    from adafruit_lsm6ds.lsm6ds3trc import LSM6DS3TRC
except ImportError:
    raise SystemExit(
        "Missing library. Copy adafruit_lsm6ds/, adafruit_bus_device/ and "
        "adafruit_register/ from the CircuitPython bundle into CIRCUITPY/lib/"
    )

i2c = busio.I2C(board.IMU_SCL, board.IMU_SDA)
imu = LSM6DS3TRC(i2c)


def read_motion():
    """Absolute tilt and roll from gravity, plus movement energy.

    Tilt and roll are derived from the gravity vector, so they are absolute
    and do not drift - no sensor fusion or filtering needed here. Energy is
    how far total acceleration departs from 1 g, i.e. how hard it is moving.
    """
    ax, ay, az = imu.acceleration

    tilt = math.degrees(math.atan2(ax, math.sqrt(ay * ay + az * az)))
    roll = math.degrees(math.atan2(ay, az))

    mag = math.sqrt(ax * ax + ay * ay + az * az)
    energy = min(1.0, abs(mag - G) / 8.0)

    return tilt, roll, energy


# ---- axis orientation -----------------------------------------------------
# Which physical gesture lands on which axis depends on how the board is
# mounted to the pen. Run it, note which value moves when you tilt versus
# twist, and if they are swapped, exchange them in the return above.
# ---------------------------------------------------------------------------

period = 1.0 / FRAME_HZ

while True:
    tilt, roll, energy = read_motion()
    print("%.2f,%.2f,%.3f" % (tilt, roll, energy))
    time.sleep(period)
