import threading
import time
import logging
from core.controller import PoseCamController
from core.osc_listener import OSCListener
from ui.tk_gui import PoseCamGUI
from detectors import (
    PoseDetectorMediapipe,
    PoseDetectorYOLO_G,
    PoseDetectorYOLO_C
)

# Configure basic logging to show INFO level messages
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# --- Model Configuration ---
# Create a mapping of user-friendly names to detector classes.
# This will be passed to the controller and then to the UI.
AVAILABLE_DETECTORS = {
    "MediaPipe Pose (Default)": PoseDetectorMediapipe,
    "YOLOv8 (Simple)": PoseDetectorYOLO_G,
    "YOLOv8 (Complex)": PoseDetectorYOLO_C,
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