"""Drives straight for 3s. If it curves, check SAVED_CAL in motors.py."""

import time

import motors
import movement

DRIVE_SECONDS = 3
TEST_SPEED = int(movement.MAX_SPEED * 0.5)

motors.setup_motors()
print(f"Driving straight for {DRIVE_SECONDS}s, Ctrl+C to stop")

try:
    movement.move(0, TEST_SPEED)
    time.sleep(DRIVE_SECONDS)
finally:
    movement.stop()  # runs even on Ctrl+C

print("Done. Straight or curved?")
