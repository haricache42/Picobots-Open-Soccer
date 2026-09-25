"""
Diagnostic only — not part of the normal robot: spins in place one way
for a few seconds, pauses, then spins the other way for the same time,
then stops. No camera, no vision, no ball-chasing involved at all.

Why this test: movement.spin(speed) sends the *same* speed to all 4
wheels. Because the wheels are mounted around the robot facing different
ways, "all the same speed" means every wheel pushes around the centre in
the same rotational direction — so the pushes cancel out sideways and
the robot should turn on the spot without sliding anywhere.

What to watch for:

  - Drifts/slides across the floor while spinning (instead of staying on
    the spot)?  One wheel is pushing harder or softer than the other 3.
    Same suspects as test_drive_straight.py: that wheel's entry in
    motors.SAVED_CAL, or a loose wheel/motor mount.
  - Spins noticeably faster one way than the other?  Also points to one
    motor behaving differently depending on direction — usually a
    calibration value (SAVED_CAL) that's slightly off.
  - One wheel not turning at all?  Check motors.setup_motors() printed
    "Motor N ready" for all 4 — the missing number is the dead one
    (order is FR, BR, BL, FL).

Tip: put a piece of tape on the floor under the robot's centre before
you start, so it's easy to see whether it wandered off the spot.

Run directly on the Pi: python test_spin.py
"""

import time

import motors
import movement

SPIN_SECONDS = 3
PAUSE_SECONDS = 1
TEST_SPEED = int(movement.MAX_SPEED * 0.3)  # slow — easier to see drift, and safer

motors.setup_motors()
print(f"Spinning in place for {SPIN_SECONDS}s each way at 30% speed. Ctrl+C to abort.")

try:
    print("Spinning one way...")
    movement.spin(TEST_SPEED)
    time.sleep(SPIN_SECONDS)

    movement.stop()
    time.sleep(PAUSE_SECONDS)

    # A negative speed runs every wheel backwards, so the robot turns the other way.
    print("Spinning the other way...")
    movement.spin(-TEST_SPEED)
    time.sleep(SPIN_SECONDS)
finally:
    # `finally` runs even if you press Ctrl+C, so the motors are never left running.
    movement.stop()

print("Done — did it stay on the spot, and turn about the same amount both ways?")
