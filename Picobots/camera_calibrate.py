"""
One-time setup script: locks the camera's exposure/white balance, samples
the ball's colour, and measures how big the ball looks at a known
distance — then saves all of it to calibration.json so vision.py can load
it on every future run.

Run this once whenever the lighting changes (e.g. new venue at a
competition).
"""

import json
import time

import cv2
import numpy as np
from picamera2 import Picamera2

import vision

SETTLE_SECONDS = 3
SAMPLE_COUNT = 15
BALL_PATCH_SIZE = 10

# Hue shouldn't be widened — it's what actually distinguishes "orange"
# from other colours, and loosening it risks confusing the ball with skin
# tones or other robots. Saturation/value are widened a bit more than
# before so a distant ball (which looks slightly dimmer/less saturated,
# just from having fewer photons reach the sensor) still falls inside the
# calibrated range.
HUE_MARGIN = 8
SAT_MARGIN = 100
VAL_MARGIN = 120

# Distance-calibration step: the ball must be held at exactly this
# distance so we can work out how big it looks at a *known* distance,
# which is the other half of the maths that lets vision.py turn "how big
# does the ball look now" into "how far away is it".
CALIBRATION_DISTANCE_CM = 50.0
DISTANCE_SAMPLE_COUNT = 15
MIN_DISTANCE_SAMPLES_REQUIRED = 5


def settle_and_lock_exposure(picamera):
    """
    Locks exposure, colour balance and other camera controls so they
    don't keep auto-adjusting during a match (which would make the HSV
    range calibrated below drift and become useless).
    """
    print(f"Settling auto-exposure/white-balance for {SETTLE_SECONDS}s... "
          f"point the camera at your real match lighting now.")

    last_metadata = None
    start = time.time()
    while time.time() - start < SETTLE_SECONDS:
        picamera.capture_array()  # just to keep frames flowing
        last_metadata = picamera.capture_metadata()
        time.sleep(0.2)

    exposure_time = last_metadata.get("ExposureTime")
    analogue_gain = last_metadata.get("AnalogueGain")
    colour_gains = last_metadata.get("ColourGains")

    picamera.set_controls({
        "AeEnable": False,
        "AwbEnable": False,
        "ExposureTime": exposure_time,
        "AnalogueGain": analogue_gain,
        "ColourGains": colour_gains,
    })

    print(f"Locked: ExposureTime={exposure_time}  AnalogueGain={round(analogue_gain, 2)}  "
          f"ColourGains=({round(colour_gains[0], 2)}, {round(colour_gains[1], 2)})\n")

    return exposure_time, analogue_gain, colour_gains


def sample_ball_hsv(picamera):
    """
    Builds a 10x10 pixel capture zone in the centre of the camera, finds
    the median HSV value of those pixels, and takes the median across
    15 frames to represent the ball's colour.
    """
    input("Hold the ball steady at the centre of the camera's view, then press Enter...")

    hue_samples, saturation_samples, value_samples = [], [], []

    for _ in range(SAMPLE_COUNT):
        frame = vision.read_frame(picamera)

        height, width = frame.shape[:2]
        cx, cy = width // 2, height // 2
        ball_half = BALL_PATCH_SIZE // 2

        ball_patch = frame[cy - ball_half: cy + ball_half, cx - ball_half: cx + ball_half]
        hsv_patch = cv2.cvtColor(ball_patch, cv2.COLOR_BGR2HSV)

        hue_samples.append(np.median(hsv_patch[:, :, 0]))
        saturation_samples.append(np.median(hsv_patch[:, :, 1]))
        value_samples.append(np.median(hsv_patch[:, :, 2]))

        time.sleep(0.1)

    hue_median = float(np.median(hue_samples))
    saturation_median = float(np.median(saturation_samples))
    value_median = float(np.median(value_samples))

    print(f"Sampled ball HSV (median of {SAMPLE_COUNT} frames): "
          f"H={round(hue_median, 1)}  S={round(saturation_median, 1)}  V={round(value_median, 1)}\n")

    return hue_median, saturation_median, value_median


def build_range_ball(h_med, s_med, v_med):
    """
    Builds the HSV range for the ball based on the median HSV values
    sampled from the ball, with a margin of error on each value.
    """
    lower = [
        max(0, h_med - HUE_MARGIN),
        max(0, s_med - SAT_MARGIN),
        max(0, v_med - VAL_MARGIN),
    ]
    upper = [
        min(179, h_med + HUE_MARGIN),
        255,
        255,
    ]
    return lower, upper


def sample_ball_apparent_diameter(picamera, lower_orange, upper_orange):
    """
    Measures how many pixels wide the ball appears when held at exactly
    CALIBRATION_DISTANCE_CM from the camera. This is the other half of
    the pinhole-camera-model distance formula: once we know how big the
    ball looks at one known distance, vision.py can invert that to
    estimate distance from apparent size at any other distance.

    Uses vision.build_ball_mask/find_best_ball_contour — the exact same
    detection logic detect_ball() uses at match time — so this
    measurement is directly comparable to what the robot will see later.

    Returns the median apparent diameter in pixels, or None if the ball
    wasn't reliably detected (too few of the sample frames found it).
    """
    input(f"Now hold the ball exactly {CALIBRATION_DISTANCE_CM:.0f}cm from the "
          f"camera lens (use a tape measure), then press Enter...")

    diameters = []
    for _ in range(DISTANCE_SAMPLE_COUNT):
        frame = vision.read_frame(picamera)

        mask = vision.build_ball_mask(frame, lower_orange, upper_orange)
        contour, diameter_px = vision.find_best_ball_contour(mask)
        if contour is not None:
            diameters.append(diameter_px)

        time.sleep(0.1)

    if len(diameters) < MIN_DISTANCE_SAMPLES_REQUIRED:
        print(f"Only detected the ball in {len(diameters)}/{DISTANCE_SAMPLE_COUNT} frames — "
              f"too few to trust. Check the ball is at {CALIBRATION_DISTANCE_CM:.0f}cm, well "
              f"lit and clearly visible, then re-run this script. Distance reporting will fall "
              f"back to raw pixels until this succeeds.")
        return None

    diameter_median = float(np.median(diameters))
    print(f"Sampled apparent ball diameter at {CALIBRATION_DISTANCE_CM:.0f}cm: "
          f"{round(diameter_median, 1)}px (from {len(diameters)}/{DISTANCE_SAMPLE_COUNT} frames)\n")
    return diameter_median


def compute_focal_length(apparent_diameter_px, known_distance_cm=CALIBRATION_DISTANCE_CM,
                          real_diameter_cm=vision.REAL_BALL_DIAMETER_CM):
    """
    Solves the pinhole camera model for focal length, in pixels:

        apparent_diameter_px = (real_diameter_cm * focal_length_px) / distance_cm

    rearranged to:

        focal_length_px = (apparent_diameter_px * distance_cm) / real_diameter_cm

    Once we have focal_length_px, vision.py can invert the same formula
    at match time to turn "how big does the ball look right now" into
    "how far away is it, in cm".
    """
    return (apparent_diameter_px * known_distance_cm) / real_diameter_cm


def main():
    picamera = Picamera2()
    picamera.configure(picamera.create_preview_configuration(
        main={"size": vision.CAMERA_RESOLUTION, "format": "RGB888"}
    ))
    picamera.start()
    time.sleep(1)  # let the sensor warm up before reading metadata

    exposure_time, analogue_gain, colour_gains = settle_and_lock_exposure(picamera)
    ball_hue_median, ball_saturation_median, ball_value_median = sample_ball_hsv(picamera)
    lower_orange, upper_orange = build_range_ball(ball_hue_median, ball_saturation_median, ball_value_median)

    apparent_diameter_px = sample_ball_apparent_diameter(
        picamera, np.array(lower_orange), np.array(upper_orange)
    )
    focal_length_px = None
    if apparent_diameter_px is not None:
        focal_length_px = compute_focal_length(apparent_diameter_px)
        # Sanity check for students: at 1024px wide with a typical Pi
        # Camera field of view, this should land roughly in 750-900.
        # Wildly outside that range usually means the ball wasn't
        # detected properly during the distance step above.
        print(f"Computed focal_length_px={round(focal_length_px, 1)} "
              f"(expect roughly 750-900 for a {vision.CAMERA_RESOLUTION[0]}px-wide frame)\n")

    calibration = {
        "exposure_time": exposure_time,
        "analogue_gain": analogue_gain,
        "colour_gains": list(colour_gains),
        "lower_orange": lower_orange,
        "upper_orange": upper_orange,
    }
    if focal_length_px is not None:
        calibration["focal_length_px"] = focal_length_px
        calibration["real_ball_diameter_cm"] = vision.REAL_BALL_DIAMETER_CM
        calibration["calibration_distance_cm"] = CALIBRATION_DISTANCE_CM

    with open("calibration.json", "w") as f:
        json.dump(calibration, f, indent=2)

    print("Saved calibration.json:")
    print(json.dumps(calibration, indent=2))


if __name__ == "__main__":
    main()
