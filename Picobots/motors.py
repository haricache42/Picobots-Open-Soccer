"""
Connects to the 4 motor driver boards over I2C and configures them with
their saved calibration values. Other files (movement.py) use `drivers`
to actually send commands.
"""

import board
import busio
from steelbar_powerful_bldc_driver import PowerfulBLDCDriver

# I2C address of each motor driver board (set by the board's address switches).
# Order: [FR, BR, BL, FL]
ADDRESSES = [25, 26, 27, 28]

# Calibration values from running the motor calibration once per motor.
# See reference/docs/driver-library for how these are generated.
SAVED_CAL = [
    {"elecangleoffset": 1608593152, "sincoscentre": 1232},
    {"elecangleoffset": 1871622656, "sincoscentre": 1255},
    {"elecangleoffset": 1444260352, "sincoscentre": 1244},
    {"elecangleoffset": 1587600640, "sincoscentre": 1251},
]

# Filled in by setup_motors(). Same order as ADDRESSES.
drivers = []
i2c = None


def setup_motors():
    """
    Connects to all 4 motor driver boards over I2C and configures them
    with the saved calibration values and PID constants.
    """
    global i2c
    i2c = busio.I2C(board.SCL, board.SDA)

    for index, address in enumerate(ADDRESSES):
        driver = PowerfulBLDCDriver(i2c, address)
        driver.set_current_limit_foc(65536)
        driver.set_id_pid_constants(1500, 200)
        driver.set_iq_pid_constants(1500, 200)
        driver.set_speed_pid_constants(4e-2, 4e-4, 3e-2)
        driver.set_ELECANGLEOFFSET(SAVED_CAL[index]["elecangleoffset"])
        driver.set_SINCOSCENTRE(SAVED_CAL[index]["sincoscentre"])
        driver.configure_operating_mode_and_sensor(3, 1)
        driver.configure_command_mode(12)
        driver.set_speed(0)
        drivers.append(driver)
        print(f"Motor {index} ready")

    print("All motors ready")
