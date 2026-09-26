"""Spins 3s each way. If it drifts off the spot, check SAVED_CAL in motors.py."""

import time

import motors
import movement

SPIN_SECONDS = 3
PAUSE_SECONDS = 1
TEST_SPEED = int(movement.MAX_SPEED * 0.3)

motors.setup_motors()
print(f"Spinning {SPIN_SECONDS}s each way, Ctrl+C to stop")

try:
    print("One way...")
    movement.spin(TEST_SPEED)
    time.sleep(SPIN_SECONDS)

    movement.stop()
    time.sleep(PAUSE_SECONDS)

    print("Other way...")
    movement.spin(-TEST_SPEED)  # negative = other direction
    time.sleep(SPIN_SECONDS)
finally:
    movement.stop()  # runs even on Ctrl+C

print("Done. Did it stay on the spot?")
