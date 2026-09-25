"""
One-time helper: saves a snapshot from the camera so you can paint over
any part of the robot's own body that the camera can see (its frame,
wheels, mounting hardware, etc.), so vision.py learns to ignore it and
never mistakes it for the ball.

How to use it:
  1. Run this script. It saves deadzone_reference.jpg.
  2. Open deadzone_reference.jpg in any image editor (MS Paint, GIMP,
     even an online one). Paint solid black over every part of the
     robot's own body visible in the photo. Leave everything else alone.
  3. Save your edited version as deadzone_mask.png, in this same folder.

That's it — vision.py automatically loads deadzone_mask.png the next
time main.py or camera_calibrate.py runs. It doesn't need to be a
perfect black-and-white image; vision.py only checks whether each pixel
is closer to black or to white. If you ever move the camera or change
the robot's shape, just redo these steps.

If you skip this entirely, nothing is masked out — vision.py treats a
missing deadzone_mask.png as "the whole frame is fair game".
"""

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

    input("Point the camera the way it'll actually sit on the robot, then press Enter...")
    frame = vision.read_frame(picam)
    cv2.imwrite(REFERENCE_IMAGE_PATH, frame)

    print(f"\nSaved {REFERENCE_IMAGE_PATH}.")
    print("Next: open it in an image editor, paint the robot's own body solid black,")
    print("and save your result as deadzone_mask.png in this same folder.")


if __name__ == "__main__":
    main()
