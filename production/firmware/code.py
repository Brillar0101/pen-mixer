# code.py - Pen Mixer v2.1 production board (ISP1807 / nRF52840 + LSM6DS3TR-C)
#
# UNTESTED: written against the v2.1 schematic before the board was assembled.
# Pin map from production/kicad/reference-nets.json and the ISP1807 symbol:
#     LED_DATA    P0.20  two chained 1x1 mm addressable RGB LEDs (LED1 battery, LED2 link)
#     BTN         P0.17  side tactile switch to GND, wake-capable
#     VBAT_SENSE  P0.03  AIN1, battery through R8/R9 = 1M/1M divider (VBAT = 2 x ADC)
#     SDA / SCL   P0.08 / P0.26  IMU I2C
#     IMU_INT1/2  P0.09 / P0.10  (NFC pins; unused here)
#
# Implements the PRD interface set on top of the motion stream:
#     I1  battery LED, four states: red <10%, orange 10-40%, green 40-80%, white >80%
#     I2  power button: press to turn on, press to turn off (System OFF sleep,
#         wake on the same button), long press to start Bluetooth pairing
#     I3  Bluetooth LED: solid blue when connected, flashing while pairing is ready
# and streams "tilt,roll,energy,sway" frames over a Nordic UART service, the
# same format as the prototype firmware, so the desktop app needs no changes.
#
# REQUIRES on CIRCUITPY/lib: adafruit_ble/, adafruit_lsm6ds/, adafruit_register/,
# adafruit_bus_device/, neopixel.mpy, adafruit_pixelbuf.mpy

import math
import time

import alarm
import analogio
import board  # noqa: F401 - kept for builds that expose board pins
import busio
import digitalio
import microcontroller
import neopixel
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService
from adafruit_lsm6ds.lsm6ds3trc import LSM6DS3TRC

PIN_LED_DATA = microcontroller.pin.P0_20
PIN_BTN = microcontroller.pin.P0_17
PIN_VBAT = microcontroller.pin.P0_03
PIN_SDA = microcontroller.pin.P0_08
PIN_SCL = microcontroller.pin.P0_26

G = 9.80665
FRAME_HZ = 100
LONG_PRESS_S = 1.5
DIVIDER = 2.0            # R8/R9 = 1M/1M
VBAT_EMPTY = 3.3         # LiPo considered 0% here
VBAT_FULL = 4.15         # and 100% here (charger terminates at 4.2)
BATTERY_POLL_S = 5.0
PAIR_BLINK_S = 0.25

# Colors as (r, g, b), kept dim: these are 1 x 1 mm LEDs behind a clear case.
RED = (40, 0, 0)
ORANGE = (40, 14, 0)
GREEN = (0, 40, 0)
WHITE = (30, 30, 30)
BLUE = (0, 0, 40)
OFF = (0, 0, 0)

pixels = neopixel.NeoPixel(PIN_LED_DATA, 2, brightness=1.0, auto_write=False)
LED_BATTERY, LED_LINK = 0, 1

button = digitalio.DigitalInOut(PIN_BTN)
button.switch_to_input(pull=digitalio.Pull.UP)

vbat_adc = analogio.AnalogIn(PIN_VBAT)


def battery_volts():
    return vbat_adc.value / 65535 * vbat_adc.reference_voltage * DIVIDER


def battery_percent():
    v = battery_volts()
    return max(0.0, min(100.0, (v - VBAT_EMPTY) / (VBAT_FULL - VBAT_EMPTY) * 100.0))


def battery_color(percent):
    if percent < 10:
        return RED
    if percent < 40:
        return ORANGE
    if percent < 80:
        return GREEN
    return WHITE


def show(battery=None, link=None):
    if battery is not None:
        pixels[LED_BATTERY] = battery
    if link is not None:
        pixels[LED_LINK] = link
    pixels.show()


def pressed():
    return not button.value


def power_off():
    """I2: press to turn off. Deep sleep until the button is pressed again."""
    show(OFF, OFF)
    time.sleep(0.3)
    while pressed():
        time.sleep(0.05)
    wake = alarm.pin.PinAlarm(pin=PIN_BTN, value=False, pull=True)
    alarm.exit_and_deep_sleep_until_alarms(wake)


def wait_release_and_classify():
    """Return "long" if held past LONG_PRESS_S, else "short"."""
    t0 = time.monotonic()
    while pressed():
        if time.monotonic() - t0 >= LONG_PRESS_S:
            return "long"
        time.sleep(0.02)
    return "short"


# IMU: same math as the prototype so the app sees identical frames.
i2c = busio.I2C(PIN_SCL, PIN_SDA)
imu = LSM6DS3TRC(i2c)

# Sway (PRD M2): leaky integral of the gyro rate about the sweep axis.
SWAY_AXIS = 2
SWAY_SCALE = 1.5
SWAY_LEAK = 0.97
sway = 0.0


def update_sway(gyro, dt):
    global sway
    sway = sway * SWAY_LEAK + gyro[SWAY_AXIS] * dt / SWAY_SCALE
    sway = max(-1.0, min(1.0, sway))
    return sway


def read_frame(dt):
    ax, ay, az = imu.acceleration
    tilt = math.degrees(math.atan2(ax, math.sqrt(ay * ay + az * az)))
    roll = math.degrees(math.atan2(ay, az))
    mag = math.sqrt(ax * ax + ay * ay + az * az)
    energy = min(1.0, abs(mag - G) / 8.0)
    return tilt, roll, energy, update_sway(imu.gyro, dt)


ble = BLERadio()
ble.name = "PenMixer"
uart = UARTService()
advert = ProvideServicesAdvertisement(uart)
period = 1.0 / FRAME_HZ

# Boot (a button press woke us, or USB power arrived): show battery, start pairing.
show(battery=battery_color(battery_percent()), link=OFF)
pairing = True
ble.start_advertising(advert)
last_battery = time.monotonic()
last_blink = time.monotonic()
blink_on = False

while True:
    now = time.monotonic()

    # I1: battery LED, refreshed every few seconds.
    if now - last_battery >= BATTERY_POLL_S:
        show(battery=battery_color(battery_percent()))
        last_battery = now

    # I2: button. Short press turns off; long press (re)starts pairing.
    if pressed():
        kind = wait_release_and_classify()
        if kind == "long":
            if ble.connected:
                for conn in ble.connections:
                    conn.disconnect()
            if not ble.advertising:
                ble.start_advertising(advert)
            pairing = True
        else:
            power_off()

    # I3: link LED. Flashing while pairing is ready, solid blue when connected.
    if ble.connected:
        if pairing:
            ble.stop_advertising()
            pairing = False
            show(link=BLUE)
        tilt, roll, energy, sway_now = read_frame(period)
        try:
            uart.write(("%.2f,%.2f,%.3f,%.3f\n" % (tilt, roll, energy, sway_now)).encode())
        except Exception:
            pass
        time.sleep(period)
    else:
        if not pairing:
            # Link dropped: advertise again and go back to flashing.
            pairing = True
            ble.start_advertising(advert)
        if now - last_blink >= PAIR_BLINK_S:
            blink_on = not blink_on
            show(link=BLUE if blink_on else OFF)
            last_blink = now
        time.sleep(0.02)
