import threading
import time
import datetime
import logging
from core.controller import PoseCamController
import os
from functools import partial
from core.osc_listener import OSCListener
from ui.tk_gui import PoseCamGUI
from detectors import (
    PoseDetectorMediapipe,
    PoseDetectorYOLO_G,
    PoseDetectorYOLO_C,
    PoseDetectorMediaPipeTask,
    # PoseDetectorYOLO_Seg
)

# Configure basic logging to show INFO level messages
# --- Setup comprehensive logging ---
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
log_filename = os.path.join(log_dir, f"poseCamPC_run_{log_timestamp}.log")

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(log_filename), logging.StreamHandler()]
)

# --- Model Configuration ---
# Create a mapping of user-friendly names to detector classes.
# This will be passed to the controller and then to the UI.
AVAILABLE_DETECTORS = {
    "MediaPipe v8n (Default)": PoseDetectorMediapipe,
    "MediaPipe Task API": partial(PoseDetectorMediaPipeTask, model='full', output_segmentation=False),
    "MediaPipe Task API +Seg (GPU)": partial(PoseDetectorMediaPipeTask, model='heavy', output_segmentation=True), # Segmentation requires the 'heavy' model
    "MediaPipe Task API +Seg (CPU)": partial(PoseDetectorMediaPipeTask, model='heavy', output_segmentation=True, delegate='CPU'),
    "YOLOv8 (Simple)": partial(PoseDetectorYOLO_G, model_filename='yolov8n-pose.pt', display_name="YOLOv8 (Simple)"),
    "YOLOv11 (Simple)": partial(PoseDetectorYOLO_G, model_filename='yolo11n-pose.pt', display_name="YOLOv11 (Simple)"), # NOTE: Requires manual download
    "YOLOv8 (Complex)": PoseDetectorYOLO_C,
    # "YOLOv8 Pose+Seg": PoseDetectorYOLO_Seg, # This model is very slow
}

controller = PoseCamController(AVAILABLE_DETECTORS)
osc_listener = OSCListener(controller)
controller.set_osc_listener(osc_listener)

# Start the OSC listener in a separate thread
osc_thread = threading.Thread(target=osc_listener.start, daemon=True)
osc_thread.start()

# Start the main processing loop in a separate thread
processing_thread = threading.Thread(target=controller.run, daemon=True)
processing_thread.start()

# Create and run the GUI on the main thread
gui = PoseCamGUI(controller)
controller.set_gui(gui)

# This will block until the GUI window is closed
gui.run()