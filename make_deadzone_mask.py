"""Saves a camera snapshot to deadzone_reference.jpg (vision.py doesn't use a mask right now)."""

import cv2
from picamera2 import Picamera2

import vision

REFERENCE_IMAGE_PATH = "deadzone_reference.jpg"


def main():
    picam = Picamera2()
    picam.configure(picam.create_preview_configuration(
        main={"size": vision.CAMERA_RESOLUTION, "format": "RGB888"}
    ))
    picam.start()

    input("Mount the camera like it is on the robot, then press Enter...")
    frame = vision.read_frame(picam)
    cv2.imwrite(REFERENCE_IMAGE_PATH, frame)

    print(f"\nSaved {REFERENCE_IMAGE_PATH}")
    print("Paint the robot's body black in an image editor,")
    print("then save it as deadzone_mask.png in this folder.")


if __name__ == "__main__":
    main()
