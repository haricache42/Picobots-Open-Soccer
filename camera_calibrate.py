"""Locks the camera and samples the ball colour into calibration.json. Rerun when the lighting changes."""

import json
import time

import cv2
import numpy as np
from picamera2 import Picamera2

import vision

SETTLE_SECONDS = 3
SAMPLE_COUNT = 15
BALL_PATCH_SIZE = 10

# Keep hue tight (that's what makes it orange), loosen the rest for far/dim balls
HUE_MARGIN = 8
SAT_MARGIN = 100
VAL_MARGIN = 120


def settle_and_lock_exposure(picamera):
    """Let auto-exposure settle, then lock it so colours don't drift."""
    print(f"Settling for {SETTLE_SECONDS}s, point the camera at the match lighting")

    last_metadata = None
    start = time.time()
    while time.time() - start < SETTLE_SECONDS:
        picamera.capture_array()  # keep frames coming
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
    """Average colour of a small square in the middle of the screen."""
    input("Hold the ball in the middle of the camera view, then press Enter...")

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

    print(f"Ball HSV: H={round(hue_median, 1)}  S={round(saturation_median, 1)}  V={round(value_median, 1)}\n")

    return hue_median, saturation_median, value_median


def build_range_ball(h_med, s_med, v_med):
    """Sampled colour plus/minus the margins."""
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
    picamera.configure(picamera.create_preview_configuration(
        main={"size": vision.CAMERA_RESOLUTION, "format": "RGB888"}
    ))
    picamera.start()
    time.sleep(1)  # warm up

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
