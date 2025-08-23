from enum import Enum
import logging
import cv2
import time
import queue
import threading
from pythonosc import udp_client
import NDIlib as ndi
from core.camera_utils import get_available_cameras

class AppState(Enum):
    INIT = 'INIT'
    READY = 'READY'
    RUNNING = 'RUNNING'
    PAUSED = 'PAUSED'
    STOPPED = 'STOPPED'

class PoseCamController:
    def __init__(self, pose_detector):
        self.pose_detector = pose_detector
        self.state = AppState.INIT
        
        # Get the list of cameras on initialization
        self.available_cameras = get_available_cameras()

        self.config = {
            'input': 'webcam',
            'loop_video': False,
            'draw_ndi_overlay': True,
            'ndi_name': 'posePC',
            'osc_ip': '127.0.0.1',
            'osc_port': 5005,
            'osc_mode': 'bundle',  # 'bundle' or 'legacy'
            'osc_listen_port': 9000,
            'video_file': None,
            'camera_id': 0, # Default to the first camera
            'fps_limit': 30
        }
        self.video_capture = None
        self.osc_client = None
        self.ndi_sender = None
        self.osc_listener = None
        self.osc_active = False
        self.ndi_active = False
        self.ndi_initialized = False
        self.gui = None
        self.frame_count = 0
        self._thread_should_stop = threading.Event()
        
        # A queue to pass frames to the GUI for preview
        self.preview_frame_queue = queue.Queue(maxsize=2)

    def set_gui(self, gui):
        self.gui = gui
        # After setting the GUI, immediately inform it of the available cameras
        if self.gui:
            self.gui.update_camera_list(self.available_cameras)

    def set_osc_listener(self, listener):
        self.osc_listener = listener


    def update_state(self, new_state):
        logging.info(f"State change: {self.state.value} -> {new_state.value}")
        self.state = new_state
        if self.gui:
            self.gui.update_ui_state(new_state)

    def update_config(self, key, value):
        # When camera_id is updated, ensure it's an integer
        if key == 'camera_id':
            value = int(value)
        
        self.config[key] = value
        logging.info(f"Config updated: {key} = {value}")
        if self.gui:
            self.gui.update_ui_config(key, value)

    def start(self):
        if self.state == AppState.RUNNING:
            logging.warning("Start command issued, but already running.")
            return

        # Simply update the state. The run() loop will handle resource creation.
        self.frame_count = 0
        self.update_state(AppState.RUNNING)

    def stop(self):
        logging.info("Stopping video stream...")
        # The run() loop will see the state change and release resources.
        self.update_state(AppState.STOPPED)

        # As a safety measure, also stop the outputs when master stop is called
        self.stop_osc()
        self.stop_ndi()

    def start_osc(self):
        if self.osc_client:
            logging.warning("OSC client is already running.")
            return
        try:
            self.osc_client = udp_client.SimpleUDPClient(self.config['osc_ip'], self.config['osc_port'])
            logging.info(f"OSC client started, sending to {self.config['osc_ip']}:{self.config['osc_port']}")
            self.osc_active = True
        except Exception as e:
            logging.error(f"Could not create OSC client: {e}")
            self.osc_client = None
            self.osc_active = False
        if self.gui:
            self.gui.update_osc_state(self.osc_active)

    def stop_osc(self):
        if self.osc_client:
            self.osc_client = None
            logging.info("OSC client closed.")
        self.osc_active = False
        if self.gui:
            self.gui.update_osc_state(self.osc_active)

    def start_ndi(self):
        if self.ndi_sender:
            logging.warning("NDI sender is already running.")
            return
        try:
            if not self.ndi_initialized:
                if not ndi.initialize():
                    raise RuntimeError("NDI initialization failed.")
                self.ndi_initialized = True
                logging.info("NDI library initialized.")
            
            send_settings = ndi.SendCreate()
            send_settings.ndi_name = self.config['ndi_name']
            self.ndi_sender = ndi.send_create(send_settings)
            if self.ndi_sender is None:
                raise RuntimeError("Failed to create NDI sender.")
            logging.info(f"NDI sender '{self.config['ndi_name']}' created.")
            self.ndi_active = True
        except Exception as e:
            logging.error(f"Could not create NDI sender: {e}")
            self.ndi_sender = None
            self.ndi_active = False
        if self.gui:
            self.gui.update_ndi_state(self.ndi_active)

    def stop_ndi(self):
        if self.ndi_sender:
            ndi.send_destroy(self.ndi_sender)
            self.ndi_sender = None
            logging.info("NDI sender destroyed.")
        self.ndi_active = False
        if self.gui:
            self.gui.update_ndi_state(self.ndi_active)

    def pause(self):
        if self.state == AppState.RUNNING:
            self.update_state(AppState.PAUSED)
        elif self.state == AppState.PAUSED:
            self.update_state(AppState.RUNNING) # Resume

    def shutdown(self):
        """Called on application exit to ensure all resources are released."""
        logging.info("Controller shutting down...")
        self._thread_should_stop.set()
        self.stop() # Stop any active processing

        if self.osc_listener:
            self.osc_listener.shutdown()

        if self.ndi_initialized:
            ndi.destroy()
            self.ndi_initialized = False
            logging.info("NDI library destroyed.")

    def send_video_via_ndi(self, frame):
        """Converts a BGR frame to RGBA and sends it via NDI."""
        if not self.ndi_sender:
            return

        try:
            # NDI expects an RGBA frame. OpenCV provides BGR.
            frame_rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)

            ndi_video_frame = ndi.VideoFrameV2()
            ndi_video_frame.data = frame_rgba
            ndi_video_frame.FourCC = ndi.FOURCC_VIDEO_TYPE_RGBX

            ndi.send_send_video_v2(self.ndi_sender, ndi_video_frame)
        except Exception as e:
            logging.error(f"Error sending NDI video frame: {e}")

    def run(self):
        """The main processing loop. This should be run in a separate thread."""
        self.update_state(AppState.READY)
        
        while not self._thread_should_stop.is_set():
            if self.state == AppState.RUNNING:
                # If we are in RUNNING state but have no capture device, create it.
                # This ensures the VideoCapture object is created and used in the same thread.
                if self.video_capture is None:
                    logging.info("Initializing video stream in background thread...")
                    source = self.config['input']
                    if source == 'webcam':
                        self.video_capture = cv2.VideoCapture(self.config['camera_id'], cv2.CAP_DSHOW)
                    elif source == 'file' and self.config['video_file']:
                        self.video_capture = cv2.VideoCapture(self.config['video_file'])
                    
                    if not self.video_capture or not self.video_capture.isOpened():
                        logging.error(f"Failed to open video source in background thread: {self.config.get('video_file') or self.config['camera_id']}")
                        # The error message for codec issues is now more relevant
                        if self.config['input'] == 'file':
                            logging.warning("Hint: The file may be corrupt or use a codec incompatible with this OpenCV backend.")
                        self.stop()
                        continue

                start_time = time.perf_counter()

                frame = self.capture_frame()
                if frame is not None:
                    self.frame_count += 1
                    # Print on the first frame and then roughly once per second
                    if self.frame_count == 1 or self.frame_count % self.config['fps_limit'] == 0:
                        logging.debug(f"Processing frame: {self.frame_count}")

                    # Process the image to find landmarks and send them via OSC
                    self.pose_detector.process_image(frame)

                    # Send landmarks via OSC based on the configured mode
                    if self.osc_active:
                        osc_mode = self.config['osc_mode']
                        if osc_mode == 'bundle':
                            self.pose_detector.send_landmarks_via_osc(self.osc_client, self.frame_count, self.config['fps_limit'])
                        elif osc_mode == 'legacy':
                            if hasattr(self.pose_detector, 'send_legacy_landmarks_via_osc'):
                                self.pose_detector.send_legacy_landmarks_via_osc(self.osc_client, self.frame_count)
                            else:
                                logging.warning(f"OSC mode is 'legacy' but detector {type(self.pose_detector).__name__} doesn't support it.")

                    # Create a frame for the local preview that *always* has the overlay
                    preview_frame = frame.copy()
                    self.pose_detector.draw_landmarks(preview_frame)
                    try:
                        self.preview_frame_queue.put_nowait(preview_frame)
                    except queue.Full:
                        pass # GUI is lagging, just drop the frame

                    # Conditionally draw landmarks on the original frame for NDI output
                    if self.config['draw_ndi_overlay']:
                        self.pose_detector.draw_landmarks(frame)
                    
                    # Send the (conditionally modified) frame to NDI
                    self.send_video_via_ndi(frame)
                else:
                    # This is a normal end-of-stream event.
                    logging.info("End of video stream. Stopping.")
                    self.stop()
                    continue

                # Frame rate limiting
                elapsed = time.perf_counter() - start_time
                sleep_time = (1.0 / self.config['fps_limit']) - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
            elif self.state == AppState.PAUSED:
                time.sleep(0.1) # Sleep to prevent busy-waiting
            else: # READY, STOPPED, INIT
                # If we are in a non-running state, ensure the capture resource is released.
                if self.video_capture:
                    logging.info("Releasing video stream in background thread...")
                    self.video_capture.release()
                    self.video_capture = None
                # Yield the CPU when idle
                time.sleep(0.05)

    def capture_frame(self):
        if self.video_capture and self.video_capture.isOpened():
            ret, frame = self.video_capture.read()
            if ret:
                return frame
            # If read failed, check for looping
            elif self.config['input'] == 'file' and self.config['loop_video']:
                logging.info("Looping video file.")
                self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.video_capture.read()
                return frame if ret else None
        return None