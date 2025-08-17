# PoseCamPC

A real-time pose detection application that captures video from a webcam or file, analyzes it to find human body landmarks, and streams the results via NDI (video) and OSC (landmark data).  It is part of my Pose2Art project which uses the outputs to drive TouchDesigner projects.  It should also be able to drive Unreal and Unity.

## Architecture

The application has been refactored into a modern, multi-threaded architecture for improved responsiveness and maintainability:

-   **`core/controller.py`**: The "engine" of the application. It runs in a background thread, managing video capture, processing, and output streams.
-   **`ui/tk_gui.py`**: The graphical user interface, built with Tkinter. It runs on the main thread and acts as a "remote control" for the controller.
-   **`detectors/`**: Contains the pose detection logic (e.g., using MediaPipe).
-   **`core/osc_listener.py`**: Runs a server in another thread to allow for remote control of the application via OSC messages.

---

## Setup and Installation (Windows)

### 1. Prerequisites

-   **NDI Tools**: The NDI runtime and SDK are required for this application to function.
    -   Download from the NDI Tools website.
    -   Run the installer and select all tools.

-   **pyenv-win**: Used to manage Python versions.
    ```powershell
    Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile "./install-pyenv-win.ps1"; &"./install-pyenv-win.ps1"
    ```
    Close and reopen your terminal for the PATH changes to take effect. Verify with `pyenv --version`.

### 2. Installation Steps

1.  **Install Python:** Use `pyenv` to install the correct Python version.
    ```powershell
    pyenv install 3.12.6
    pyenv local 3.12.6
    ```

2.  **Run Setup Script:** This script creates a virtual environment and installs dependencies from `requirements.txt`.  
    ```powershell
    scripts\setup.bat
    ```

3.  **Install NDI for Python:** The `ndi-python` library must be installed manually from the local wheel file.
    > **Note:** We intentionally do not list `ndi-python` in `requirements.txt` because it is not available on PyPI for all Python versions. This command is dealt with in the setup.bat
    ```powershell
    # Make sure your venv is active before running this
    pip install ndi/NDIlib_python-5.6.0-cp312-cp312-win_amd64.whl
    ```

---

## Preflight Tests

Before running the main application, you can use the included scripts to verify that NDI and OSC are working correctly on your system. Open two separate terminals in the project root.

**Terminal 1 (Sender):** `scripts\run_tx.bat`

**Terminal 2 (Receiver/Validator):** `scripts\run_rx.bat`

You should see the receiver terminal printing periodic NDI resolution/FPS updates and confirming the arrival of OSC messages.

---

## Running the Application

Use the provided run script to launch the application with its UI.
```powershell
scripts\run.bat
```
Alternatively, you can run it directly with Python or in Visual Studio Code.
```bash
# Ensure your virtual environment is active
python poseCamPC.py
```

## User Interface Guide

The main window is split into two sections: the controls on the left and the video preview on the right.

### Main Controls

-   **Start Video**: Begins capturing and processing video from the selected input source.
-   **Pause Video**: Temporarily freezes the video stream. Click again to resume.
-   **Stop Video**: Halts the video stream and releases the camera or file.

### Input Source

This section determines where the video comes from.

-   **Webcam / File Radio Buttons**: Selects the active input mode. The controls for the inactive mode will be disabled.
-   **Webcam -> Device Dropdown**: When "Webcam" is selected, this dropdown lists all available cameras on your system. Select one to use it.
-   **File -> Select... Button**: When "File" is selected, click this to open a file browser and choose a video file. The path of the selected file will appear in the text box next to it.
-   **Loop Video Checkbox**: If a video file is selected, checking this box will cause the video to loop automatically when it reaches the end.

### Output Settings

This section configures the NDI and OSC data streams. These can be started and stopped independently of the main video stream.

-   **NDI Stream**:
    -   **Text Box**: Set the name for your NDI video stream as it will appear on the network.
    -   **Start/Stop Buttons**: Manually start or stop the NDI output.
    -   **Draw Overlay on NDI Checkbox**: When checked, the detected skeleton is drawn directly onto the NDI video stream. Uncheck to send a clean video feed.
-   **OSC**:
    -   **IP / Port Text Boxes**: Set the destination IP address and port for the OSC landmark data.
    -   **OSC Send Mode**: Choose the format for outgoing OSC messages.
        -   **Bundle (New)**: The modern, efficient default. Sends all landmark data for a single frame in one network packet (an OSC Bundle). Recommended for new projects.
        -   **Legacy (Old)**: Sends each piece of landmark data as a separate OSC message. This is less efficient but provides backward compatibility with older projects.
    -   **Start/Stop Buttons**: Manually start or stop sending OSC messages.

### Video Preview

The large area on the right displays the live video feed with the detected pose landmarks overlaid.

-   It will show a "Waiting for video stream..." message on startup.
-   The preview will begin once you press "Start Video".

---
## OSC Specification

The application uses OSC for two purposes: sending pose data out and receiving remote control commands.

### Pose Data (Output)

The format of the outgoing pose data depends on the **OSC Send Mode** selected in the UI.

#### Bundle Mode (Default)

This mode is highly efficient and recommended for all new projects. It sends all data for a single frame as one OSC Bundle.

Each message within the bundle has the following structure:

| Part | Example | Type | Description |
|---|---|---|---|
| Address | `/pose/p1/0` | string | The OSC address. `p1` is the 1-based person ID. `0` is the 0-based landmark ID from the MediaPipe Pose model. |
| Argument 1 | `0.512` | float | The normalized X coordinate of the landmark. |
| Argument 2 | `0.245` | float | The normalized Y coordinate of the landmark. |
| Argument 3 | `-0.876` | float | The normalized Z coordinate of the landmark. `z` represents depth, with smaller values being closer to the camera. |

A single OSC bundle will contain many of these messages, one for each detected landmark (typically 33 per person).

#### Legacy Mode

This mode sends many individual messages per frame and is intended for backward compatibility. It is less efficient than Bundle Mode. A single video frame will generate multiple OSC messages, including metadata and data for each landmark.

| Address | Example Arguments | Type | Description |
|---|---|---|---|
| `/framecount` | `1234` | int | The current frame number of the video stream. |
| `/image-width` | `640` | int | The width of the processed video frame in pixels. |
| `/image-height` | `480` | int | The height of the processed video frame in pixels. |
| `/numLandmarks` | `33` | int | The total number of landmarks detected for a person. |
| `/p{id}/{name}` | `[0.61, 0.45, -0.75]` | float array (x, y, z) | The coordinates for a specific landmark. `id` is the 1-based person ID. `name` is the human-readable landmark name (e.g., `shoulder_l`). |

### Landmark ID Mapping

The following table maps the 0-based `landmark_id` sent in **Bundle Mode** to the corresponding body part name used by MediaPipe Pose. This is the same mapping used to generate names in **Legacy Mode**.

| ID | Name | ID | Name |
|:---|:---|:---|:---|
| 0 | `head` | 17 | `mp_pinky_l` |
| 1 | `mp_eye_inner_l` | 18 | `mp_pinky_r` |
| 2 | `eye_l` | 19 | `handtip_l` |
| 3 | `mp_eye_outer_l` | 20 | `handtip_r` |
| 4 | `mp_eye_inner_r` | 21 | `thumb_l` |
| 5 | `eye_r` | 22 | `thumb_r` |
| 6 | `mp_eye_outer_r` | 23 | `hip_l` |
| 7 | `mp_ear_l` | 24 | `hip_r` |
| 8 | `mp_ear_r` | 25 | `knee_l` |
| 9 | `mp_mouth_l` | 26 | `knee_r` |
| 10 | `mp_mouth_r` | 27 | `ankle_l` |
| 11 | `shoulder_l` | 28 | `ankle_r` |
| 12 | `shoulder_r` | 29 | `mp_heel_l` |
| 13 | `elbow_l` | 30 | `mp_heel_r` |
| 14 | `elbow_r` | 31 | `foot_l` |
| 15 | `wrist_l` | 32 | `foot_r` |
| 16 | `wrist_r` | | |

### Remote Control (Input)

The application listens for OSC messages on port **9000** (by default) to allow for remote control.

| Address | Arguments | Description |
|---|---|---|
| `/posecam/control/start` | (none) | Starts the main video processing loop. |
| `/posecam/control/stop` | (none) | Stops the main video processing loop. |
| `/posecam/control/pause` | (none) | Pauses/resumes the video processing loop. |
| `/posecam/input/select` | `(string) source` | Changes the input source. `source` must be "webcam" or "file". |
| `/posecam/input/file` | `(string) path` | Sets the path for the video file input. |
| `/posecam/output/osc/ip` | `(string) ip` | Sets the destination IP for outgoing OSC data. |
| `/posecam/output/osc/port` | `(int) port` | Sets the destination port for outgoing OSC data. |

---
# Future Improvements

The pose_detector library includes stubs for dealing with multiple person/skeleton.  There are a number of tools that can do this.  Additionally, there are developing tools that can capture 3d data (approximately) from a video stream.
