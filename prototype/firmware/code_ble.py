# code_ble.py - Seeed XIAO nRF52840 Sense, wireless variant, vertical rest pose
# (copied onto CIRCUITPY as code.py; prototype/flash/code.py is the same file)
#
# The pen is held upright in the writing grip, board along the pen, and
# that grip is the balanced point: for half a second after the app
# connects the firmware averages the sensors, and whatever angle the pen
# sits at right then becomes zero. Hold the pen naturally while the app
# says "connected" and everything starts flat.
#
# Gestures in this pose:
#     tilt  (lean forward/back)     gravity leaking onto the board face
#     sway  (swing left/right)      gyro, leaky integral, drifts back flat
#     twist (rotate about the pen)  gyro, leaky integral. With the pen
#                                   vertical a twist spins around gravity
#                                   itself, so the accelerometer cannot
#                                   see it; it has to come from the gyro.
#
# The frame format is unchanged ("tilt,roll,energy,sway"): twist is
# scaled into the roll field, so the app needs no changes.
#
# REQUIRES on CIRCUITPY/lib :
#     adafruit_ble/  adafruit_lsm6ds/  adafruit_bus_device/  adafruit_register/

import math
import time

import board
import busio
import digitalio

from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService
from adafruit_lsm6ds.lsm6ds3trc import LSM6DS3TRC

G = 9.80665
FRAME_HZ = 100          # lower than USB - BLE cannot sustain 250 Hz cleanly

# Axis assignment for the vertical grip: x runs along the pen, y across
# it, z out of the board face. If a gesture reacts to the wrong motion,
# swap that one constant (0=x, 1=y, 2=z) - axis_probe.py shows which
# column your gesture actually lands on.
TILT_ACCEL_AXIS = 2     # forward/back lean leaks gravity onto the face
SWAY_GYRO_AXIS = 2      # left/right swing rotates about the face normal
TWIST_GYRO_AXIS = 0     # twist rotates about the pen's length

SWAY_SCALE = 1.5        # rad of sweep for full mids
SWAY_LEAK = 0.97        # drifts back to flat in about a third of a second
TWIST_SCALE = 3.1       # rad of twist for full treble, about half a turn
TWIST_LEAK = 0.99       # holds a twist longer than sway before going flat

NEUTRAL_S = 0.5         # grip-averaging window right after connecting

imu_pwr = digitalio.DigitalInOut(board.IMU_PWR)
imu_pwr.direction = digitalio.Direction.OUTPUT
imu_pwr.value = True
time.sleep(0.1)

i2c = busio.I2C(board.IMU_SCL, board.IMU_SDA)
imu = LSM6DS3TRC(i2c)

ble = BLERadio()
ble.name = "PenMixer-Lexy"
uart = UARTService()
advert = ProvideServicesAdvertisement(uart)

period = 1.0 / FRAME_HZ


def raw_tilt():
    """Forward/back lean in degrees, from how much gravity sits on the face."""
    accel = imu.acceleration
    mag = math.sqrt(sum(a * a for a in accel)) or G
    leak = max(-1.0, min(1.0, accel[TILT_ACCEL_AXIS] / mag))
    return math.degrees(math.asin(leak))


def capture_neutral():
    """Average a short window of sensor data in the player's grip.

    Returns the grip's own tilt (subtracted from every later frame so
    the grip reads balanced) and the gyro's idle bias (cheap gyros rest
    slightly off zero, and an integrator turns that into steady drift).
    """
    n = max(1, int(NEUTRAL_S * FRAME_HZ))
    tilt_sum = 0.0
    bias = [0.0, 0.0, 0.0]
    for _ in range(n):
        tilt_sum += raw_tilt()
        gyro = imu.gyro
        for i in range(3):
            bias[i] += gyro[i]
        time.sleep(period)
    return tilt_sum / n, [b / n for b in bias]


while True:
    ble.start_advertising(advert)
    while not ble.connected:
        time.sleep(0.1)
    ble.stop_advertising()

    tilt0, bias = capture_neutral()
    sway = 0.0
    twist = 0.0

    while ble.connected:
        accel = imu.acceleration
        mag = math.sqrt(sum(a * a for a in accel)) or G
        tilt = raw_tilt() - tilt0
        energy = min(1.0, abs(mag - G) / 8.0)

        gyro = imu.gyro
        sway = sway * SWAY_LEAK + (gyro[SWAY_GYRO_AXIS] - bias[SWAY_GYRO_AXIS]) * period / SWAY_SCALE
        sway = max(-1.0, min(1.0, sway))
        twist = twist * TWIST_LEAK + (gyro[TWIST_GYRO_AXIS] - bias[TWIST_GYRO_AXIS]) * period / TWIST_SCALE
        twist = max(-1.0, min(1.0, twist))
        roll = twist * 90.0

        try:
            uart.write(("%.2f,%.2f,%.3f,%.3f\n" % (tilt, roll, energy, sway)).encode())
        except Exception:
            break
        time.sleep(period)
