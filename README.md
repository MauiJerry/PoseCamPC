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
-   **OSC**:
    -   **IP / Port Text Boxes**: Set the destination IP address and port for the OSC landmark data.
    -   **Start/Stop Buttons**: Manually start or stop sending OSC messages.

### Video Preview

The large area on the right displays the live video feed with the detected pose landmarks overlaid.

-   It will show a "Waiting for video stream..." message on startup.
-   The preview will begin once you press "Start Video".

### OSC Remote Control

The application listens for OSC messages on port `9000` for remote control. See `core/osc_listener.py` for the available commands and paths, which include:

-   `/posecam/control/start`
-   `/posecam/control/stop`
-   `/posecam/input/select [webcam|file]`
-   `/posecam/input/file [path_to_file]`
---
# Future Improvements

The pose_detector library includes stubs for dealing with multiple person/skeleton.  There are a number of tools that can do this.  Additionally, there are developing tools that can capture 3d data (approximately) from a video stream.
