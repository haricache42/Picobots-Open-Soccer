"""Ball detection."""

import json
import math

import cv2
import numpy as np
from picamera2 import Picamera2

CAMERA_RESOLUTION = (1024, 768)
MIN_BALL_AREA = 25  # ignore blobs smaller than this

# Set by detect_ball()
ball_angle = 0.0
ball_area = 0.0
ball_visible = False


def setup_camera():
    """Start the camera and load calibration.json."""
    picam = Picamera2()
    picam.configure(picam.create_preview_configuration(main={"size": CAMERA_RESOLUTION, "format": "RGB888"}))
    picam.start()

    try:
        with open("calibration.json") as file:
            cal = json.load(file)
        picam.set_controls({
            "AeEnable": False,
            "AwbEnable": False,
            "ExposureTime": cal["exposure_time"],
            "AnalogueGain": cal["analogue_gain"],
            "ColourGains": tuple(cal["colour_gains"]),
        })
        lower, upper = np.array(cal["lower_orange"]), np.array(cal["upper_orange"])
    except FileNotFoundError:
        print("No calibration.json, using default orange")
        lower, upper = np.array([4, 120, 80]), np.array([24, 255, 255])

    return picam, lower, upper, None  # main.py wants 4 values


def read_frame(picam):
    """Camera is mounted sideways, so rotate."""
    frame = picam.capture_array()
    return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)


def detect_ball(frame, lower, upper, distance_scale=None):
    """Find the biggest orange blob and draw a line to it."""
    global ball_angle, ball_area, ball_visible

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower, upper)  # orange = white
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    height, width = frame.shape[:2]
    cx, cy = width // 2, height // 2
    ball_visible = False

    if contours:
        ball = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(ball)
        if area >= MIN_BALL_AREA:
            m = cv2.moments(ball)
            bx, by = int(m["m10"] / m["m00"]), int(m["m01"] / m["m00"])  # blob centre

            ball_angle = math.degrees(math.atan2(bx - cx, cy - by)) % 360  # 0 = straight ahead
            ball_area = area
            ball_visible = True

            cv2.drawContours(frame, [ball], -1, (0, 255, 255), 2)
            cv2.line(frame, (cx, cy), (bx, by), (255, 0, 0), 2)

    return frame
