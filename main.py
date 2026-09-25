"""
The actual game loop: start everything up, then run two things at once —
streaming the camera to a browser (camera_view.html), and deciding how to
move based on where vision.py says the ball is.
"""

import asyncio
import signal
import sys

import cv2
import websockets

import motors
import movement
import vision

# The robot still detects the ball on the full-resolution frame from
# vision.py — this only controls how big/detailed the copy sent to
# camera.html is. Shrinking it and compressing it harder is what actually
# fixes the "video stream feels laggy" problem: a 1024x768 full-quality
# JPEG is a lot of data to push over WiFi every frame, and none of that
# extra detail is needed just for a human to see where the ball is.
STREAM_WIDTH = 640
STREAM_JPEG_QUALITY = 70  # 0-100; lower = smaller/faster, higher = crisper

# The robot's top plate is wide enough that the camera can't see the ball
# once it's very close — it's not gone, just hidden under the plate. If
# the ball disappears right after looking this big on screen (a strong
# "it went under the plate" signal), motor_task() spends a couple of
# seconds nudging diagonally left/right instead of spinning in place —
# spinning can't reveal something hidden directly ahead, since the blind
# spot turns with the robot, but nudging sideways shifts the robot enough
# to peek around it while still closing in on the ball's last direction.
#
# BLIND_SPOT_AREA_THRESHOLD is a starting guess — tune it using the
# area=... number already shown on the camera.html overlay: slide the
# ball toward the robot, note the area right before it vanishes under
# the plate, and set this a bit below that.
BLIND_SPOT_AREA_THRESHOLD = 6000
BLIND_SPOT_NUDGE_ANGLE = 35  # degrees off the ball's last-known direction
BLIND_SPOT_NUDGE_SPEED = int(movement.MAX_SPEED * 0.35)
BLIND_SPOT_SWITCH_TICKS = 15  # ticks per side before alternating (~0.3s)
BLIND_SPOT_MAX_TICKS = 100  # give up and fall back to spin-search after this (~2s)

# Browser tabs currently watching the camera feed.
clients = set()


async def ws_handler(ws):
    """Adds/removes browser tabs that connect to watch the camera feed."""
    clients.add(ws)
    print("Browser connected")
    try:
        await ws.wait_closed()
    finally:
        clients.remove(ws)


async def stream_cam(picam, lower, upper, distance_scale):
    """Grabs frames, finds the ball, and sends the frame to any watching browsers."""
    while True:
        frame = vision.read_frame(picam)
        frame = vision.detect_ball(frame, lower, upper, distance_scale)

        # Shrink just this outgoing copy — vision.detect_ball() already
        # ran on the full-size frame above, so detection accuracy isn't
        # affected at all, only how much data has to travel over WiFi.
        stream_height = int(frame.shape[0] * STREAM_WIDTH / frame.shape[1])
        preview = cv2.resize(frame, (STREAM_WIDTH, stream_height))

        encode_params = [cv2.IMWRITE_JPEG_QUALITY, STREAM_JPEG_QUALITY]
        success, image_data = cv2.imencode(".jpg", preview, encode_params)
        if success and clients:
            jpg = image_data.tobytes()
            await asyncio.gather(*[c.send(jpg) for c in clients])

        await asyncio.sleep(0.03)


async def motor_task():
    """
    Every tick: if the ball is visible, drive toward it.

    If it just disappeared while looking very close (see
    BLIND_SPOT_AREA_THRESHOLD above), assume it's hidden under the front
    plate rather than actually gone, and spend a short window nudging
    diagonally side to side — toward where it was last seen, angled left
    then right — to try to see around the blind spot. If that window
    runs out without finding it again, fall back to the normal spin-search.
    """
    blind_spot_ticks_left = 0
    ticks_in_recovery = 0
    nudge_toward_left = True
    was_visible = False

    while True:
        if vision.ball_visible:
            movement.move(vision.ball_angle, int(movement.MAX_SPEED * 0.7))
            blind_spot_ticks_left = 0

        else:
            if was_visible and vision.ball_area > BLIND_SPOT_AREA_THRESHOLD:
                # The ball just vanished while it looked very close —
                # start (or restart) the blind-spot recovery window.
                blind_spot_ticks_left = BLIND_SPOT_MAX_TICKS
                ticks_in_recovery = 0

            if blind_spot_ticks_left > 0:
                if ticks_in_recovery % BLIND_SPOT_SWITCH_TICKS == 0:
                    nudge_toward_left = not nudge_toward_left
                offset = -BLIND_SPOT_NUDGE_ANGLE if nudge_toward_left else BLIND_SPOT_NUDGE_ANGLE
                movement.move(vision.ball_angle + offset, BLIND_SPOT_NUDGE_SPEED)
                blind_spot_ticks_left -= 1
                ticks_in_recovery += 1
            else:
                movement.spin(int(movement.MAX_SPEED * 0.3))

        was_visible = vision.ball_visible
        await asyncio.sleep(0.02)


async def main():
    motors.setup_motors()
    picam, lower_orange, upper_orange, distance_scale = vision.setup_camera()

    # compression=None: the frames we send are already JPEG-compressed,
    # so having the websocket library try to compress them again just
    # burns CPU on the Pi for no size benefit — another source of lag.
    server = await websockets.serve(ws_handler, "0.0.0.0", 8765, compression=None)
    print("WebSocket stream on port 8765 — open camera.html to watch.")
    print("Ctrl+C to stop.")

    await asyncio.gather(
        stream_cam(picam, lower_orange, upper_orange, distance_scale),
        motor_task(),
    )
    await server.wait_closed()


def shutdown(sig, frame):
    print("\nShutting down...")
    movement.stop()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    asyncio.run(main())
