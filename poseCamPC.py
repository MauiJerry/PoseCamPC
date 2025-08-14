import threading
import time
from core.controller import PoseCamController
from core.osc_listener import OSCListener
from ui.tk_gui import PoseCamGUI
from detectors.mediapipe_detector import PoseDetectorMediapipe

pose_detector = PoseDetectorMediapipe()
controller = PoseCamController(pose_detector)

# Start the OSC listener in a separate thread
osc_thread = threading.Thread(target=OSCListener(controller).start, daemon=True)
osc_thread.start()

# Start the main processing loop in a separate thread
processing_thread = threading.Thread(target=controller.run, daemon=True)
processing_thread.start()

# Create and run the GUI on the main thread
gui = PoseCamGUI(controller)
controller.set_gui(gui)

# This will block until the GUI window is closed
gui.run()