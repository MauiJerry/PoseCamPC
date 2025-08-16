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

-   **Address Scheme**: `/pose/p{person_id}/{landmark_id}`
-   **Arguments**: `(float) x`, `(float) y`, `(float) z`
-   **Description**: Each message in the bundle represents one landmark. `person_id` is 1-based. `landmark_id` is a 0-based index corresponding to the MediaPipe Pose model.

*Example bundle content for one person:*
```
/pose/p1/0, [0.512, 0.245, -0.876]
/pose/p1/1, [0.523, 0.213, -0.854]
/pose/p1/2, [0.524, 0.213, -0.854]
... (up to landmark 32)
```

#### Legacy Mode

This mode sends many individual messages per frame and is intended for backward compatibility.

-   **Address Scheme**: Varies. Includes landmark data and metadata.
-   **Description**: Sends one message for each landmark, plus several messages for metadata.

*Example messages sent for a single frame:*
```
/framecount, (int) 1234
/image-height, (int) 480
/image-width, (int) 640
/p1/head, [0.512, 0.245, -0.876]
/p1/shoulder_l, [0.610, 0.450, -0.750]
... (and so on for all other named landmarks)
/numLandmarks, (int) 33
```

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
