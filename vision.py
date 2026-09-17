"""
Everything about seeing the ball: setting up the camera, and finding the
ball's angle/distance in each frame.

ball_angle / ball_distance / ball_area / ball_visible always hold the
result of the most recent detect_ball() call — other files just read
these (e.g. `vision.ball_angle`) whenever they need to know where the
ball is.
"""

import json
import math

import cv2
import numpy as np
from picamera2 import Picamera2

ball_angle = 0.0
ball_distance = 0.0
ball_area = 0.0
ball_visible = False


def setup_camera():
    """
    Starts the camera and loads calibration.json (created by
    camera_calibrate.py) if it exists, so colour detection matches what
    was calibrated for the current lighting.
    """
    picam = Picamera2()
    picam.configure(picam.create_preview_configuration())
    picam.start()

    try:
        with open("calibration.json") as file:
            calibration = json.load(file)

        picam.set_controls({
            "AeEnable": False,
            "AwbEnable": False,
            "ExposureTime": calibration["exposure_time"],
            "AnalogueGain": calibration["analogue_gain"],
            "ColourGains": tuple(calibration["colour_gains"]),
        })

        lower_orange = np.array(calibration["lower_orange"])
        upper_orange = np.array(calibration["upper_orange"])
        print("Loaded calibration.json. Camera locked, using calibrated HSV range.")

    except FileNotFoundError:
        print("No calibration.json found. Run camera_calibrate.py first. Using fallback HSV range for now.")
        lower_orange = np.array([4, 120, 80])
        upper_orange = np.array([24, 255, 255])

    return picam, lower_orange, upper_orange


def read_frame(picam):
    """Grabs one frame from the camera, rotated to match how it's mounted."""
    frame = picam.capture_array()
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    # Rotated because the camera is physically mounted 90 degrees rotated.
    return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)


def detect_ball(frame, lower, upper):
    """
    Looks for the ball in `frame` using an HSV colour range, and updates
    ball_angle / ball_distance / ball_area / ball_visible.
    Also draws what it found onto the frame, for the live view.
    Returns the annotated frame.
    """
    global ball_angle, ball_distance, ball_area, ball_visible

    height, width = frame.shape[:2]
    cx, cy = width // 2, height // 2

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower, upper)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.circle(frame, (cx, cy), 4, (0, 255, 0), -1)

    ball_visible = False
    ball_area = 0.0

    if contours:
        best = max(contours, key=cv2.contourArea)
        ball_area = cv2.contourArea(best)
        if ball_area > 100:
            mom = cv2.moments(best)
            if mom["m00"] != 0:
                bx = int(mom["m10"] / mom["m00"])
                by = int(mom["m01"] / mom["m00"])
                dx = bx - cx
                dy = by - cy

                ball_angle = math.degrees(math.atan2(dx, -dy)) % 360
                ball_distance = (dx ** 2 + dy ** 2) ** 0.5
                ball_visible = True

                cv2.drawContours(frame, [best], -1, (0, 255, 255), 2)
                cv2.circle(frame, (bx, by), 5, (0, 0, 255), -1)
                cv2.line(frame, (cx, cy), (bx, by), (255, 0, 0), 2)
                cv2.putText(
                    frame,
                    f"angle={round(ball_angle, 1)}  dist={round(ball_distance, 1)}px  area={round(ball_area, 1)}",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
                )

    return frame
