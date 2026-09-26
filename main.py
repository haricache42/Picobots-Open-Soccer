"""Main loop: streams the camera and chases the ball."""

import asyncio
import signal
import sys

import cv2
import websockets

import motors
import movement
import vision

# Smaller stream = less lag over WiFi
STREAM_WIDTH = 640
STREAM_JPEG_QUALITY = 70  # 0-100

# Ball can hide under the front plate when it's close.
# If it vanishes while this big, wiggle left/right to find it before spinning.
BLIND_SPOT_AREA_THRESHOLD = 6000  # tune with area= on camera.html
BLIND_SPOT_NUDGE_ANGLE = 35  # degrees
BLIND_SPOT_NUDGE_SPEED = int(movement.MAX_SPEED * 0.35)
BLIND_SPOT_SWITCH_TICKS = 15  # ~0.3s per side
BLIND_SPOT_MAX_TICKS = 100  # ~2s, then spin

# Open browser tabs
clients = set()


async def ws_handler(ws):
    """Track browser tabs."""
    clients.add(ws)
    print("Browser connected")
    try:
        await ws.wait_closed()
    finally:
        clients.remove(ws)


async def stream_cam(picam, lower, upper, distance_scale):
    """Find the ball and send each frame to the browser."""
    while True:
        frame = vision.read_frame(picam)
        frame = vision.detect_ball(frame, lower, upper, distance_scale)

        # Only shrink the copy we send
        stream_height = int(frame.shape[0] * STREAM_WIDTH / frame.shape[1])
        preview = cv2.resize(frame, (STREAM_WIDTH, stream_height))

        encode_params = [cv2.IMWRITE_JPEG_QUALITY, STREAM_JPEG_QUALITY]
        success, image_data = cv2.imencode(".jpg", preview, encode_params)
        if success and clients:
            jpg = image_data.tobytes()
            await asyncio.gather(*[c.send(jpg) for c in clients])

        await asyncio.sleep(0.03)


async def motor_task():
    """Chase the ball, check the blind spot if it vanishes up close, otherwise spin."""
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
                # Probably went under the plate
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

    # Frames are already JPEGs, no point compressing again
    server = await websockets.serve(ws_handler, "0.0.0.0", 8765, compression=None)
    print("Streaming on port 8765, open camera.html")
    print("Ctrl+C to stop")

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
