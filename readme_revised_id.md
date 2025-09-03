# PoseCamPC

A flexible and high-performance PC application for capturing human pose data from webcams or video files and broadcasting it via NDI and OSC.

## Features

- **Multiple Input Sources**: Use any connected webcam or a local video file.
- **Real-time Pose Detection**: Powered by Google's MediaPipe for accurate and fast pose landmark detection.
- **Dual Output**:
    - **NDI**: Stream the video output, with or without a pose overlay, to any NDI-compatible software.
    - **OSC**: Send detailed pose landmark data over the network for use in creative coding environments like TouchDesigner, Max/MSP, Processing, etc.
- **Configurable**: Easy-to-use GUI to control all input and output settings.
- **Remote Control**: Control the application remotely via OSC commands.

## OSC Output

The application provides two modes for sending OSC data, configurable via the GUI.

### 1. Bundle Mode (Default)

This is the recommended mode. It sends all data for a single frame in one efficient OSC bundle.

- **Metadata**: Includes frame count, timestamp, number of detected persons, and image dimensions.
- **Landmark Data**: Landmark coordinates are sent to addresses formatted as `/pose/p<person_id>/<landmark_id>`.
    - `person_id` starts at 1.
    - `landmark_id` is the numerical index of the landmark (e.g., 0 for the nose).

### 2. Legacy Mode

This mode sends one OSC message per landmark, which may be easier to parse in some environments but is less efficient.

- Landmark coordinates are sent to addresses formatted as `/p1/<landmark_name>`.
- Only supports a single person.

---

### Landmark ID to Name Mapping

To help you interpret the landmark data, the application provides the ID-to-name mapping in several ways:

1.  **`landmark_idname.csv` File (Recommended)**:
    Upon starting, the application automatically generates a file named `landmark_idname.csv` in its root directory. This file contains the definitive mapping of each numerical `landmark_id` to its corresponding string `name` (e.g., `0,nose`). **This is the primary reference for your client application.**

2.  **`/pose/landmark_names` OSC Message**:
    When using the `bundle` mode, the application periodically sends an OSC message to the address `/pose/landmark_names`. The arguments of this message are an ordered list of all landmark names. The index of each name in the list corresponds to its `landmark_id`. This allows a client to build its mapping table dynamically.

#### TouchDesigner Integration (`@landmark_names_td.csv`)

For users integrating with TouchDesigner, a supplementary file named `@landmark_names_td.csv` is provided. This file serves as a helpful cross-reference, mapping the landmark index to both the official MediaPipe name and the specific channel names used within our TouchDesigner projects. This can simplify the process of routing OSC data to the correct parameters.

---

The following table maps the 0-based `landmark_id` sent in **Bundle Mode** to the corresponding body part name. This is the same mapping used to generate names in **Legacy Mode** and is written to `landmark_idname.csv`.

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

## Setup

1.  Ensure you have Python installed.
2.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run the application:
    ```bash
    python poseCamPC.py
    ```

## Remote Control (Input)

The application can be controlled remotely by sending OSC messages to the listening port (default `9000`).

- `/posecam/control/start`: Starts the video stream.
- `/posecam/control/stop`: Stops the video stream.
- `/posecam/control/pause`: Toggles the pause state of the video stream.