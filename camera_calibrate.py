"""
One-time setup script: locks the camera's exposure/white balance and
samples the ball's colour, then saves both to calibration.json so
vision.py can load them on every future run.

Run this once whenever the lighting changes (e.g. new venue at a
competition).
"""

import json
import time

import cv2
import numpy as np
from picamera2 import Picamera2

SETTLE_SECONDS = 3
SAMPLE_COUNT = 15
BALL_PATCH_SIZE = 10

HUE_MARGIN = 8
SAT_MARGIN = 80
VAL_MARGIN = 100


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
        frame = picamera.capture_array()
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

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


def main():
    picamera = Picamera2()
    picamera.configure(picamera.create_preview_configuration())
    picamera.start()
    time.sleep(1)  # let the sensor warm up before reading metadata

    exposure_time, analogue_gain, colour_gains = settle_and_lock_exposure(picamera)
    ball_hue_median, ball_saturation_median, ball_value_median = sample_ball_hsv(picamera)
    lower_orange, upper_orange = build_range_ball(ball_hue_median, ball_saturation_median, ball_value_median)

    calibration = {
        "exposure_time": exposure_time,
        "analogue_gain": analogue_gain,
        "colour_gains": list(colour_gains),
        "lower_orange": lower_orange,
        "upper_orange": upper_orange,
    }

    with open("calibration.json", "w") as f:
        json.dump(calibration, f, indent=2)

    print("Saved calibration.json:")
    print(json.dumps(calibration, indent=2))


if __name__ == "__main__":
    main()
