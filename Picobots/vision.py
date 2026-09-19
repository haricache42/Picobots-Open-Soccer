"""
Everything about seeing the ball: setting up the camera, and finding the
ball's angle/distance in each frame.

ball_angle / ball_distance / ball_area / ball_visible always hold the
result of the most recent detect_ball() call — other files just read
these (e.g. `vision.ball_angle`) whenever they need to know where the
ball is. ball_distance_unit tells you whether ball_distance is in real
centimetres or, as a fallback, raw pixels — see setup_camera().
"""

import json
import math

import cv2
import numpy as np
from picamera2 import Picamera2

# Real-world diameter of the RCJ Soccer Open ball, used to turn "how big
# the ball looks" into "how far away it is". If your ball is a different
# size, update this (and re-run camera_calibrate.py).
REAL_BALL_DIAMETER_CM = 4.27

# How wide/tall to capture frames at. Bigger frames mean a far-away ball
# still covers enough pixels to be reliably detected, at the cost of more
# CPU work per frame (and therefore a lower frame rate). 1024x768 is a
# good middle ground for both the v2 and v3 Pi Camera modules. If the
# live stream looks choppy or the robot reacts sluggishly, drop this to
# (640, 480); if you want to detect the ball even farther away and can
# afford slower frames, try (1280, 960).
CAMERA_RESOLUTION = (1024, 768)

# Mask cleanup constants (see build_ball_mask). All in pixels, must be odd.
BLUR_KERNEL_SIZE = 5
MORPH_OPEN_KERNEL_SIZE = 5
MORPH_CLOSE_KERNEL_SIZE = 7

# A contour has to clear both of these to be considered "the ball" (see
# find_best_ball_contour). Area alone used to be the only check, which
# meant a big non-ball orange blob could beat a smaller real ball, and a
# high area cutoff (100) was needed to avoid noise — that hid the ball
# early once it got small/far away. Checking roundness too lets the area
# cutoff drop a lot, since noise speckles are almost never round.
MIN_BALL_AREA = 25
MIN_FILL_RATIO = 0.6

# Optional: a black-and-white image, the same size as the camera frame,
# for telling detect_ball() to ignore parts of the frame where the robot
# can see its own body (its own frame, wheels, mounting hardware, etc).
# White = look here, black = ignore here. Make one with
# make_deadzone_mask.py. If this file doesn't exist, nothing is masked
# out — see setup_camera() and build_ball_mask().
DEADZONE_MASK_PATH = "deadzone_mask.png"

# If the ball drops out of view for a few frames (motion blur, something
# briefly blocking it), don't immediately declare it "lost" — that would
# make the robot jerk into search-spin mode over a single bad frame.
# 8 frames is roughly a quarter to half a second at the speeds this loop
# runs, enough to bridge a brief occlusion without chasing a stale
# position for long if the ball is genuinely gone.
MAX_MISSED_FRAMES = 8

# How much each new reading affects the smoothed value (0-1). Higher = ­
# reacts faster but jitters more; lower = smoother but laggier. 0.4 keeps
# only a few frames of "memory", enough to iron out single-frame jitter
# without adding noticeable delay to a moving ball.
EMA_ALPHA = 0.4

ball_angle = 0.0
ball_distance = 0.0
ball_distance_unit = "px"
ball_area = 0.0
ball_visible = False

# The loaded deadzone image (see DEADZONE_MASK_PATH above), or None if
# there isn't one. Set once by setup_camera(); read by build_ball_mask().
deadzone_mask = None

# Internal bookkeeping for the grace period and smoothing above — other
# files shouldn't need to read these directly, they just affect how the
# four globals above behave.
_frames_since_ball_seen = MAX_MISSED_FRAMES + 1
_ball_angle_ema_x = 1.0
_ball_angle_ema_y = 0.0


def setup_camera():
    """
    Starts the camera and loads calibration.json (created by
    camera_calibrate.py) if it exists, so colour detection matches what
    was calibrated for the current lighting.

    Returns (picam, lower_orange, upper_orange, distance_scale).
    distance_scale is real_ball_diameter_cm * focal_length_px — the two
    numbers detect_ball() needs to convert apparent ball size into a
    real-world distance in cm (see the module docstring in
    camera_calibrate.py for the maths). It's None if calibration.json is
    missing, or if it predates this distance-calibration feature — in
    that case detect_ball() falls back to reporting distance in pixels.
    """
    global deadzone_mask

    picam = Picamera2()
    picam.configure(picam.create_preview_configuration(
        main={"size": CAMERA_RESOLUTION, "format": "RGB888"}
    ))
    picam.start()

    deadzone_mask = cv2.imread(DEADZONE_MASK_PATH, cv2.IMREAD_GRAYSCALE)
    if deadzone_mask is not None:
        print(f"Loaded {DEADZONE_MASK_PATH} — will ignore the robot's own body there.")
    else:
        print(f"No {DEADZONE_MASK_PATH} found — not masking anything out. "
              f"Run make_deadzone_mask.py if the camera can see the robot's own body.")

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

        focal_length_px = calibration.get("focal_length_px")
        real_ball_diameter_cm = calibration.get("real_ball_diameter_cm", REAL_BALL_DIAMETER_CM)
        if focal_length_px is not None:
            distance_scale = real_ball_diameter_cm * focal_length_px
            print(f"Distance calibration found — reporting ball_distance in cm.")
        else:
            distance_scale = None
            print("calibration.json has no focal_length_px (older calibration, or that step "
                  "was skipped) — reporting ball_distance in raw pixels instead of cm. "
                  "Re-run camera_calibrate.py to enable real-world distance.")

    except FileNotFoundError:
        print("No calibration.json found. Run camera_calibrate.py first. Using fallback HSV "
              "range for now, and reporting ball_distance in raw pixels.")
        lower_orange = np.array([4, 120, 80])
        upper_orange = np.array([24, 255, 255])
        distance_scale = None

    return picam, lower_orange, upper_orange, distance_scale


def read_frame(picam):
    """
    Grabs one frame from the camera, rotated to match how it's mounted.

    No colour conversion needed here, even though we configured the
    camera with format="RGB888": that's a confusingly-named Picamera2
    quirk where an "RGB888" stream actually delivers pixels already in
    BGR order (the order OpenCV wants everywhere else in this file).
    Converting it again used to flip red and blue a second time, which
    is why the live view looked colour-inverted.
    """
    frame = picam.capture_array()
    # Rotated because the camera is physically mounted 90 degrees rotated.
    return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)


def build_ball_mask(frame, lower, upper):
    """
    Turns a raw camera frame into a clean black/white mask of "pixels that
    look like the ball's colour".

    Blurs first to smooth out sensor noise before thresholding (smoother
    input HSV values make for a cleaner mask than trying to fix a blocky
    mask after the fact), then cleans up the threshold result with a
    morphological open (erases tiny speckles of noise) and close (fills
    small holes — e.g. a bright highlight on the ball splitting its mask
    into a ring instead of a solid disc).

    If a deadzone mask is loaded (see DEADZONE_MASK_PATH), pixels marked
    black there are cleared out here too, so the robot's own body never
    gets mistaken for the ball.
    """
    blurred = cv2.GaussianBlur(frame, (BLUR_KERNEL_SIZE, BLUR_KERNEL_SIZE), 0)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower, upper)

    if deadzone_mask is not None:
        height, width = mask.shape[:2]
        resized_deadzone = cv2.resize(deadzone_mask, (width, height))
        # Threshold so it doesn't matter exactly how dark you painted —
        # anything darker than mid-grey counts as "ignore this part".
        _, binary_deadzone = cv2.threshold(resized_deadzone, 127, 255, cv2.THRESH_BINARY)
        mask = cv2.bitwise_and(mask, binary_deadzone)

    open_kernel = np.ones((MORPH_OPEN_KERNEL_SIZE, MORPH_OPEN_KERNEL_SIZE), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel)

    close_kernel = np.ones((MORPH_CLOSE_KERNEL_SIZE, MORPH_CLOSE_KERNEL_SIZE), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)

    return mask


def find_best_ball_contour(mask):
    """
    Looks through every contour in `mask` and returns the one that most
    plausibly is the ball, as (contour, apparent_diameter_px) — or
    (None, 0.0) if nothing qualifies.

    A candidate has to be big enough to not be leftover noise
    (MIN_BALL_AREA) and round enough to not be some other blob of orange,
    like a stripe on a wall or another robot's marker (MIN_FILL_RATIO).
    Roundness is measured by how much of its own minimum enclosing circle
    the contour actually fills — a real ball fills most of that circle;
    a jagged or elongated blob does not.
    """
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_contour = None
    best_diameter = 0.0
    best_area = 0.0

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < MIN_BALL_AREA:
            continue

        (_, _), radius = cv2.minEnclosingCircle(contour)
        enclosing_area = math.pi * radius ** 2
        if enclosing_area == 0:
            continue

        fill_ratio = area / enclosing_area
        if fill_ratio < MIN_FILL_RATIO:
            continue

        if area > best_area:
            best_contour = contour
            best_area = area
            best_diameter = radius * 2

    return best_contour, best_diameter


def detect_ball(frame, lower, upper, distance_scale=None):
    """
    Looks for the ball in `frame` using an HSV colour range, and updates
    ball_angle / ball_distance / ball_area / ball_visible. Also draws what
    it found onto the frame, for the live view. Returns the annotated frame.

    distance_scale (from setup_camera()) is used to convert the ball's
    apparent pixel size into a real distance in cm via the pinhole camera
    model: distance = (real_diameter * focal_length) / apparent_diameter.
    Pass None to fall back to reporting distance as raw pixels from the
    frame centre (the old behaviour).

    If the ball briefly isn't found, the last known reading is kept for
    up to MAX_MISSED_FRAMES frames (see that constant) instead of
    immediately flipping ball_visible to False, and readings are smoothed
    with an exponential moving average to reduce frame-to-frame jitter.
    """
    global ball_angle, ball_distance, ball_distance_unit, ball_area, ball_visible
    global _frames_since_ball_seen, _ball_angle_ema_x, _ball_angle_ema_y

    height, width = frame.shape[:2]
    cx, cy = width // 2, height // 2
    cv2.circle(frame, (cx, cy), 4, (0, 255, 0), -1)

    mask = build_ball_mask(frame, lower, upper)
    contour, apparent_diameter_px = find_best_ball_contour(mask)

    if contour is not None:
        mom = cv2.moments(contour)
        if mom["m00"] != 0:
            bx = int(mom["m10"] / mom["m00"])
            by = int(mom["m01"] / mom["m00"])
            dx = bx - cx
            dy = by - cy

            raw_angle = math.degrees(math.atan2(dx, -dy)) % 360
            raw_area = cv2.contourArea(contour)

            if distance_scale is not None and apparent_diameter_px > 0:
                raw_distance = distance_scale / apparent_diameter_px
                ball_distance_unit = "cm"
            else:
                raw_distance = math.hypot(dx, dy)
                ball_distance_unit = "px"

            # Was the ball already being tracked (within its grace
            # period), or is this a fresh detection after being properly
            # lost? Fresh detections snap straight to the new reading
            # instead of blending with stale old data.
            still_tracking = _frames_since_ball_seen <= MAX_MISSED_FRAMES

            # Smooth the angle by averaging its position on the unit
            # circle rather than the degree number directly — averaging
            # raw degrees breaks at the 0/360 seam (359 and 1 would
            # naively average to 180, the opposite of correct), but
            # there's no seam on the circle itself.
            angle_rad = math.radians(raw_angle)
            new_x, new_y = math.cos(angle_rad), math.sin(angle_rad)

            if still_tracking:
                _ball_angle_ema_x = EMA_ALPHA * new_x + (1 - EMA_ALPHA) * _ball_angle_ema_x
                _ball_angle_ema_y = EMA_ALPHA * new_y + (1 - EMA_ALPHA) * _ball_angle_ema_y
                ball_distance = EMA_ALPHA * raw_distance + (1 - EMA_ALPHA) * ball_distance
                ball_area = EMA_ALPHA * raw_area + (1 - EMA_ALPHA) * ball_area
            else:
                _ball_angle_ema_x, _ball_angle_ema_y = new_x, new_y
                ball_distance = raw_distance
                ball_area = raw_area

            ball_angle = math.degrees(math.atan2(_ball_angle_ema_y, _ball_angle_ema_x)) % 360
            ball_visible = True
            _frames_since_ball_seen = 0

            cv2.drawContours(frame, [contour], -1, (0, 255, 255), 2)
            cv2.circle(frame, (bx, by), 5, (0, 0, 255), -1)
            cv2.line(frame, (cx, cy), (bx, by), (255, 0, 0), 2)
            cv2.putText(
                frame,
                f"angle={round(ball_angle, 1)}  dist={round(ball_distance, 1)}{ball_distance_unit}  "
                f"area={round(ball_area, 1)}",
                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
            )
    else:
        _frames_since_ball_seen += 1
        if _frames_since_ball_seen > MAX_MISSED_FRAMES:
            ball_visible = False

    return frame
