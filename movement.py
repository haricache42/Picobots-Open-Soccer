"""
Turns motor speeds into robot movement: driving toward an angle, spinning
in place, and stopping. Built on top of motors.py.
"""

import math
import motors

MAX_SPEED = 50000000


def move(degree, speed=MAX_SPEED):
    """
    Drives the robot toward `degree` (0 = the direction the camera faces),
    using trig to work out how fast each of the 4 wheels needs to spin.
    """
    angle_rad = math.radians(degree + 90)
    x = math.floor(math.cos(angle_rad) * speed)
    y = math.floor(math.sin(angle_rad) * speed)
    motors.drivers[0].set_speed(y + x)       # FR
    motors.drivers[1].set_speed(y - x)       # BR
    motors.drivers[2].set_speed(-(y + x))    # BL
    motors.drivers[3].set_speed(-(y - x))    # FL


def spin(speed):
    """Spins the robot in place (used when the ball isn't visible)."""
    for driver in motors.drivers:
        driver.set_speed(speed)


def stop():
    """Stops all 4 motors."""
    for driver in motors.drivers:
        driver.set_speed(0)
