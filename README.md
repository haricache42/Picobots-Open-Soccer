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
- `camera.html` to watch the camera in a browser

## Hardware Setup
A Raspberry Pi runs 4 BLDC motors over I2C (omni drive) and uses the Pi Camera to find the ball.

### Motor Configuration (I2C)
| I2C Address | Position |
| ----------- | ------------- |
| 25 | Front Right |
| 26 | Back Right |
| 27 | Back Left |
| 28 | Front Left |

# INSTALLING
1. Clone the repo onto the Pi (or use VS Code Remote-SSH)
2. `pip install opencv-python numpy websockets adafruit-blinka steelbar-powerful-bldc-driver`
    - `picamera2` comes with Raspberry Pi OS. If it's missing: `sudo apt install -y python3-picamera2`
3. Run `camera_calibrate.py` to make `calibration.json`. Redo it when the lighting changes.

# DEPLOYING & USAGE
On the Pi, go to `/home/jarvis/Robotics/`
- `python main.py` to start, Ctrl+C to stop
- `python test_drive_straight.py` / `python test_spin.py` to test the motors

Viewing:
- SSH into `pico`
- Open `camera.html` in a browser on the same network

# ADDITIONAL INFORMATION
