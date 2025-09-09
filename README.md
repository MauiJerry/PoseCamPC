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

### Pose Model

This section allows you to choose the underlying AI model for pose detection. The application must be stopped to change models.

-   **Pose Model Dropdown**: Select which pose detection model to use.
    -   **MediaPipe Pose (Default)**: A balanced, single-person model from Google with 33 landmarks.
    -   **MediaPipe Pose (Multi)**: The same model, but structured to handle multiple people if the underlying library supports it in the future.
    -   **YOLOv8 (Simple)**: A fast, multi-person model with 17 landmarks (COCO standard). This version uses a simple, high-level API.
    -   **YOLOv8 (Complex)**: The same YOLOv8 model, but with more exposed parameters for fine-tuning detection performance.

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

## Configuration

While most common settings are available in the GUI, some core parameters are set directly in the code. The main configuration dictionary is located at the top of `core/controller.py`.

One of the most important settings is `fps_limit`:

-   **`fps_limit`** (int): This value serves two purposes:
    1.  It caps the main processing loop to this framerate to conserve CPU.
    2.  It determines how often periodic OSC metadata (like image dimensions and aspect ratio) is sent. For a value of `30`, this data is sent roughly once per second.

```python
# In core/controller.py
'fps_limit': 30
```

---
## OSC Specification

The application uses OSC for two purposes: sending pose data out and receiving remote control commands.

### Pose Data (Output)

The format of the outgoing pose data depends on the **OSC Send Mode** selected in the UI.

#### Bundle Mode (Default)

This mode is highly efficient and recommended for all new projects. It sends all data for a single frame as one OSC Bundle.

A single OSC bundle will contain a mix of metadata and landmark data messages.

**Metadata Messages**

| Address | Example Argument | Type | Description | Frequency |
|---|---|---|---|---|
| `/pose/frame_count` | `1234` | int | The current frame number of the video stream. | Every Frame |
| `/pose/num_persons` | `1` | int | The number of skeletons detected in the frame. | Every Frame |
| `/pose/timestamp` | `1709924385.532` | float | A high-precision Unix timestamp (seconds since 1970-01-01). Ideal for machine calculations. | Every Frame |
| `/pose/timestamp_str` | `"2024.03.08.13.59.45.532"` | string | A human-readable timestamp string in `YYYY.MM.DD.HH.MM.SS.ms` format. | Periodically (~1s) |
| `/pose/image_width` | `640` | int | The width of the processed video frame in pixels. | Periodically (~1s) |
| `/pose/image_height` | `480` | int | The height of the processed video frame in pixels. | Periodically (~1s) |
| `/pose/aspect_ratio` | `1.3333` | float | The calculated aspect ratio (`width / height`). | Periodically (~1s) |
| `/pose/model_name` | `"MediaPipe Pose"` | string | The name of the active pose detection model. | Periodically (~1s) |


**Landmark Data Message**

For each detected landmark, a message with the following structure is added to the bundle.

| Part | Example | Type | Description |
|---|---|---|---|
| Address | `/pose/p1/0` | string | The OSC address. `p1` is the 1-based person ID. `0` is the 0-based landmark ID. |
| Arguments | `0.512, 0.245, -0.876` | 3 floats | The normalized (X, Y, Z) coordinates of the landmark. `z` represents depth, with smaller values being closer to the camera. |

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

To help you interpret the landmark data, the application provides the ID-to-name mapping in several ways:

1.  **`landmark_idname.csv` File**:
    Upon starting or changing models, the application automatically generates a file named `landmark_idname.csv` in its root directory. This file contains the definitive mapping for the **currently selected model**. This is the primary reference for your client application.

2.  **`/pose/landmark_names` OSC Message**:
    When using the `bundle` mode, the application periodically sends an OSC message to the address `/pose/landmark_names`. The arguments of this message are an ordered list of all landmark names. The index of each name in the list corresponds to its `landmark_id`. This allows a client to build its mapping table dynamically.

#### TouchDesigner Integration (`@landmark_names_td.csv`)

For users integrating with TouchDesigner, a supplementary file named `@landmark_names_td.csv` is provided. This file serves as a helpful cross-reference, mapping the landmark index to both the official MediaPipe name and the specific channel names used within our TouchDesigner projects. This can simplify the process of routing OSC data to the correct parameters.

---

The landmark maps depend on the model selected.

#### MediaPipe Landmark Map (33 Landmarks)
Used by `MediaPipe Pose` and `MediaPipe Pose (Multi)` models.

| ID | Name | ID | Name |
|:---|:---|:---|:---|
| 0 | `nose` | 17 | `pinky_l` |
| 1 | `eye_inner_l` | 18 | `pinky_r` |
| 2 | `eye_l` | 19 | `handtip_l` |
| 3 | `eye_outer_l` | 20 | `handtip_r` |
| 4 | `eye_inner_r` | 21 | `thumb_l` |
| 5 | `eye_r` | 22 | `thumb_r` |
| 6 | `eye_outer_r` | 23 | `hip_l` |
| 7 | `ear_l` | 24 | `hip_r` |
| 8 | `ear_r` | 25 | `knee_l` |
| 9 | `mouth_l` | 26 | `knee_r` |
| 10 | `mouth_r` | 27 | `ankle_l` |
| 11 | `shoulder_l` | 28 | `ankle_r` |
| 12 | `shoulder_r` | 29 | `heel_l` |
| 13 | `elbow_l` | 30 | `heel_r` |
| 14 | `elbow_r` | 31 | `foot_l` |
| 15 | `wrist_l` | 32 | `foot_r` |
| 16 | `wrist_r` | | |

#### COCO Landmark Map (17 Landmarks)
Used by `YOLOv8 (Simple)` and `YOLOv8 (Complex)` models.

| ID | Name | ID | Name |
|:---|:---|:---|:---|
| 0 | `nose` | 9 | `wrist_l` |
| 1 | `eye_l` | 10 | `wrist_r` |
| 2 | `eye_r` | 11 | `hip_l` |
| 3 | `ear_l` | 12 | `hip_r` |
| 4 | `ear_r` | 13 | `knee_l` |
| 5 | `shoulder_l` | 14 | `knee_r` |
| 6 | `shoulder_r` | 15 | `ankle_l` |
| 7 | `elbow_l` | 16 | `ankle_r` |
| 8 | `elbow_r` | | |


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
