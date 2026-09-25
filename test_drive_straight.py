"""
Diagnostic only — not part of the normal robot: drives dead straight
(bearing 0, at half speed) for a few seconds, then stops. No camera, no
vision, no ball-chasing involved at all.

Why this test: movement.move(0, speed) is pure math — it should always
produce a straight line with zero rotation, no matter what main.py's
ball-following logic is doing. So this isolates the question "is the
robot twisting" down to just two places:

  - Still twists here?  It's not main.py or vision.py (neither is even
    imported below) — look at motors.py instead: SAVED_CAL is 4 sets of
    per-motor values (elecangleoffset, sincoscentre) from the motor
    calibration procedure (reference/docs/driver-library). If one of
    those 4 is wrong for the motor it's assigned to, that one wheel spins
    at the wrong speed/direction relative to what movement.py asked for,
    which unbalances the push on that corner and turns a straight drive
    into a curve or a spin. Re-running the calibration procedure for
    each motor (one at a time, matching SAVED_CAL's [FR, BR, BL, FL]
    order to motors.ADDRESSES) is the fix if so.
  - Drives straight here, but still twists while chasing the ball?
    Then it's not motors.py/movement.py at all — the problem is upstream,
    in what angle vision.py is feeding move() each tick. A ball detection
    that jitters between frames (e.g. a too-loose HSV range in
    calibration.json picking up a second orange blob, or lighting
    flicker) makes move() keep re-aiming at a different angle every
    tick, which looks exactly like twisting even though each individual
    command is a straight line.

Run directly on the Pi: python test_drive_straight.py
"""

import time

import motors
import movement

DRIVE_SECONDS = 3
TEST_SPEED = int(movement.MAX_SPEED * 0.5)  # modest speed — easier to judge "did it curve"

motors.setup_motors()
print(f"Driving straight (bearing 0) for {DRIVE_SECONDS}s at half speed. Ctrl+C to abort.")

try:
    movement.move(0, TEST_SPEED)
    time.sleep(DRIVE_SECONDS)
finally:
    movement.stop()

print("Done — did it drive in a straight line, or curve/twist?")
