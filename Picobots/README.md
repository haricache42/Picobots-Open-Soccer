# Team H - Picobots
## General Information
| | |
| ----------- | ---- |
| Year | 2026 |
| Year Level | 11 |
| Team Letter | H |
| Team Name | Picobots |

Team Members:
- Hariharasudan Sannasi
- Jeffrey Li
- Xin Xiu Lin
- Laurence Teo

# REQUIREMENTS
## Software
- Visual Studio Code
- Python 3
- OpenCV (`opencv-python`)
- NumPy
- `picamera2`
- `websockets`
- `adafruit-blinka` (`board`, `busio`)
- `steelbar-powerful-bldc-driver`
- Custom browser debug viewer (`camera.html`) — streams live camera feed with ball detection overlay over WebSocket

## Hardware Setup
Raspberry Pi controls four BLDC motors over I2C for omnidirectional drive, and reads the Pi Camera Module for ball detection.

### Motor Configuration (I2C)
| I2C Address | Position |
| ----------- | ------------- |
| 25 | Front Right |
| 26 | Back Right |
| 27 | Back Left |
| 28 | Front Left |

# INSTALLING
For a Raspberry Pi robot:
1. Clone the repo onto the Pi (or edit directly via VS Code Remote-SSH)
2. Install dependencies:
    - `pip install opencv-python numpy picamera2 websockets adafruit-blinka steelbar-powerful-bldc-driver`
3. Run `camera_calibrate.py` once to lock exposure/other camera settings and sample the ball's HSV range. This generates `calibration.json`, which the main script loads on startup.
4. (Optional) Run `make_deadzone_mask.py` once if the camera can see part of the robot's own body — it saves a snapshot you paint over to tell vision.py to ignore that part of the frame. See the comments at the top of that file for how.

# DEPLOYING & USAGE
Pi: Navigate to `/home/jarvis/Robotics/main.py`
- Run `python main.py` to start the robot.
- Press Ctrl+C to stop the robot

Open:
- Connect to the robot via SSH at `pico`
- Open `camera.html` in a browser on the same network to view the live stream with ball-tracking

# ADDITIONAL INFORMATION
