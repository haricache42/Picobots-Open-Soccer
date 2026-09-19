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

        success, image_data = cv2.imencode(".jpg", frame)
        if success and clients:
            jpg = image_data.tobytes()
            await asyncio.gather(*[c.send(jpg) for c in clients])

        await asyncio.sleep(0.03)


async def motor_task():
    """Every tick: if the ball is visible, drive toward it. Otherwise, spin to look for it."""
    while True:
        if not vision.ball_visible:
            movement.spin(int(movement.MAX_SPEED * 0.3))
        else:
            movement.move(vision.ball_angle, int(movement.MAX_SPEED * 0.7))
        await asyncio.sleep(0.02)


async def main():
    motors.setup_motors()
    picam, lower_orange, upper_orange, distance_scale = vision.setup_camera()

    server = await websockets.serve(ws_handler, "0.0.0.0", 8765)
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
