# code_ble.py - Seeed XIAO nRF52840 Sense, wireless variant
#
# Same data, sent over Bluetooth LE instead of the USB cable. Get the wired
# build working first, so that a failure here is definitely the radio and not
# the sensor.
#
# REQUIRES on CIRCUITPY/lib, in addition to the wired build's libraries:
#     adafruit_ble/             (folder)
#
# NOTE: bridge.py reads a USB serial port. To use this you need a BLE client
# on the laptop side instead - the pairing shows up as a Nordic UART service.
# BLE also adds roughly 10 ms of latency versus USB's ~1 ms.

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

imu_pwr = digitalio.DigitalInOut(board.IMU_PWR)
imu_pwr.direction = digitalio.Direction.OUTPUT
imu_pwr.value = True
time.sleep(0.1)

i2c = busio.I2C(board.IMU_SCL, board.IMU_SDA)
imu = LSM6DS3TRC(i2c)

ble = BLERadio()
ble.name = "PenMixer"
uart = UARTService()
advert = ProvideServicesAdvertisement(uart)

period = 1.0 / FRAME_HZ

# Horizontal motion for the mid band (PRD M2): integrate the gyro rate about
# the sweep axis with a leak, so a stroke to the right builds a positive value
# and holding still lets it drift back to zero. SWAY_AXIS picks which gyro
# axis reads left/right for the way the board sits on the pen; watch the
# "Sway (mid)" meter in the app and change it if the meter reacts to the
# wrong gesture. Units: rad/s in, -1..1 out, full scale about 1.5 rad of sweep.
SWAY_AXIS = 2
SWAY_SCALE = 1.5
SWAY_LEAK = 0.97
sway = 0.0


def update_sway(gyro, dt):
    global sway
    sway = sway * SWAY_LEAK + gyro[SWAY_AXIS] * dt / SWAY_SCALE
    sway = max(-1.0, min(1.0, sway))
    return sway


while True:
    ble.start_advertising(advert)
    while not ble.connected:
        time.sleep(0.1)
    ble.stop_advertising()

    while ble.connected:
        ax, ay, az = imu.acceleration
        tilt = math.degrees(math.atan2(ax, math.sqrt(ay * ay + az * az)))
        roll = math.degrees(math.atan2(ay, az))
        mag = math.sqrt(ax * ax + ay * ay + az * az)
        energy = min(1.0, abs(mag - G) / 8.0)
        sway_now = update_sway(imu.gyro, period)
        try:
            uart.write(("%.2f,%.2f,%.3f,%.3f\n" % (tilt, roll, energy, sway_now)).encode())
        except Exception:
            break
        time.sleep(period)
