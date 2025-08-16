import threading
import time
import logging
from core.controller import PoseCamController
from core.osc_listener import OSCListener
from ui.tk_gui import PoseCamGUI
from detectors import PoseDetectorMediapipe

# Configure basic logging to show INFO level messages
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

pose_detector = PoseDetectorMediapipe()
controller = PoseCamController(pose_detector)
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