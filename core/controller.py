from enum import Enum
import logging
import os
import cv2
import datetime
import csv
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
    def __init__(self, available_detectors):
        self.available_detectors = available_detectors
        self.state = AppState.INIT

        # Default config values
        default_detector_name = "MediaPipe Pose (Default)"
        if default_detector_name not in self.available_detectors:
            # Fallback if the default isn't present for some reason
            default_detector_name = list(self.available_detectors.keys())[0]

        # This will be instantiated based on the config
        self.pose_detector = None
        self.video_width = 0
        self.video_height = 0

        # Get the list of cameras on initialization
        self.available_cameras = get_available_cameras()

        # Find default video file and camera
        default_video = self._find_default_video_file()
        default_camera_id = self._find_default_camera_id()

        self.config = {
            'input': 'file',
            'loop_video': True,
            'draw_ndi_overlay': True,
            'ndi_name': 'posePC',
            'osc_ip': '127.0.0.1',
            'osc_port': 5005,
            'osc_listen_port': 9000,
            'video_file': default_video,
            'camera_id': default_camera_id, # Use the determined default camera
            'fps_limit': 30,
            'detector_model': default_detector_name
        }

        # --- Performance Logging Setup ---
        log_timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        self.perf_log_file = f"performance_log_{log_timestamp}.csv"
        self.model_perf_stats = {} # e.g., {'model_name': {'total_time': 0.0, 'frame_count': 0}}
        
        try:
            with open(self.perf_log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                # Add the header for the event/metadata lines
                writer.writerow(['# event_type', 'timestamp_us', 'model_name', 'overlay_status', 'source_info', 'resolution'])
                writer.writerow(['model', 'frame_num', 'time_for_frame_ms', 'fps', 'persons', 'running_avg_ms', 'running_avg_fps'])

        except Exception as e:
            logging.error(f"Failed to create performance log file: {e}")
            self.perf_log_file = None # Disable logging if file can't be created

        self._initialize_detector()
        self.pose_detector.save_landmark_map_to_csv()

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
        # After setting the GUI, immediately inform it of available devices and models
        if self.gui:
            self.gui.update_camera_list(self.available_cameras)
            self.gui.update_detector_list(
                detector_names=list(self.available_detectors.keys()),
                current_detector_name=self.config['detector_model']
            )

    def set_osc_listener(self, listener):
        self.osc_listener = listener

    def _find_default_video_file(self):
        """Looks for the first video file in the ./videoSamples directory."""
        sample_dir = 'videoSamples'
        if not os.path.isdir(sample_dir):
            logging.warning(f"Video samples directory not found: {sample_dir}")
            return None
        
        try:
            # Sort to get a consistent file if multiple exist
            for filename in sorted(os.listdir(sample_dir)):
                # A simple check to avoid hidden files, can be made more robust
                if not filename.startswith('.'):
                    full_path = os.path.join(sample_dir, filename)
                    if os.path.isfile(full_path):
                        logging.info(f"Found default video file: {full_path}")
                        return full_path
        except Exception as e:
            logging.error(f"Error reading video samples directory: {e}")
        
        logging.warning(f"No video files found in {sample_dir}")
        return None

    def _find_default_camera_id(self):
        """
        Finds the preferred default camera.
        Prefers cameras whose name starts with "USB", otherwise falls back to the first available.
        """
        if not self.available_cameras:
            logging.warning("No cameras found. Defaulting camera_id to 0.")
            return 0

        # Sort by camera ID to ensure consistent ordering
        sorted_cameras = sorted(self.available_cameras.items())

        # Look for a USB camera first
        for cam_id, cam_name in sorted_cameras:
            if cam_name.lower().startswith("usb"):
                logging.info(f"Found preferred USB camera: '{cam_name}' (ID: {cam_id})")
                return cam_id
        
        # If no USB camera is found, fall back to the first one in the list
        first_cam_id, first_cam_name = sorted_cameras[0]
        logging.info(f"No USB camera found. Defaulting to first available: '{first_cam_name}' (ID: {first_cam_id})")
        return first_cam_id

    def _initialize_detector(self):
        """Instantiates or re-instantiates the pose detector based on the current config."""
        model_name = self.config.get('detector_model')
        if model_name not in self.available_detectors:
            logging.error(f"Detector model '{model_name}' not found in available detectors. Halting.")
            # This is a critical error, as we can't proceed without a valid detector.
            raise ValueError(f"Invalid detector model '{model_name}' specified in config.")

        DetectorClass = self.available_detectors[model_name]
        try:
            logging.info(f"Initializing pose detector: {model_name}...")
            self.pose_detector = DetectorClass()
            logging.info(f"Successfully initialized pose detector: {model_name}")
        except Exception as e:
            logging.error(f"Failed to initialize detector '{model_name}': {e}")
            # Re-raise to halt execution, as the app can't run without a detector.
            raise

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

        # If the overlay setting changes, log it as a performance event
        if key == 'draw_ndi_overlay':
            self._log_perf_event() # Log this change to reset averages

    def _log_perf_event(self):
        """Logs a configuration change event and resets the running average for the current model."""
        if not self.perf_log_file:
            return

        model_name = self.config['detector_model']

        # Always reset the running average for the current model when an event occurs
        self.model_perf_stats[model_name] = {'total_time': 0.0, 'frame_count': 0}
        logging.info(f"Performance event occurred. Running average for '{model_name}' reset.")

        # Only write the full log entry if the stream is active (we have resolution info)
        if self.video_width == 0:
            return

        plot_status = self.config['draw_ndi_overlay']
        timestamp = time.time_ns() // 1000  # microseconds

        # --- Gather source and resolution info ---
        source_type = self.config['input']
        source_info = ""
        if source_type == 'webcam':
            cam_id = self.config['camera_id']
            cam_name = self.available_cameras.get(cam_id, f"ID {cam_id}")
            source_info = f"Webcam: {cam_name}"
        elif source_type == 'file':
            file_path = self.config.get('video_file')
            source_info = f"File: {os.path.basename(file_path) if file_path else 'N/A'}"

        resolution_info = f"{self.video_width}x{self.video_height}" if self.video_width > 0 else "Stream not active"

        try:
            with open(self.perf_log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([f'# Change', timestamp, model_name, plot_status, source_info, resolution_info])
        except Exception as e:
            logging.error(f"Failed to write performance event to log: {e}")

    def _log_perf_frame(self, frame_time_s):
        """Logs the performance data for a single processed frame."""
        if not self.perf_log_file:
            return

        model_name = self.config['detector_model']
        frame_time_ms = frame_time_s * 1000
        
        # Calculate instantaneous FPS, handle division by zero
        fps = 1.0 / frame_time_s if frame_time_s > 0 else 0

        # Get the number of persons detected in the last processed frame
        num_persons = len(self.pose_detector.latest_landmarks)

        # Initialize stats for a model if not present
        if model_name not in self.model_perf_stats:
            self.model_perf_stats[model_name] = {'total_time': 0.0, 'frame_count': 0}

        # Update stats
        stats = self.model_perf_stats[model_name]
        stats['total_time'] += frame_time_s
        stats['frame_count'] += 1

        # Calculate running average
        running_avg_s = stats['total_time'] / stats['frame_count']
        running_avg_ms = running_avg_s * 1000
        # Calculate running average FPS, handle division by zero
        running_avg_fps = 1.0 / running_avg_s if running_avg_s > 0 else 0

        try:
            with open(self.perf_log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([model_name, self.frame_count, frame_time_ms, fps, num_persons, running_avg_ms, running_avg_fps])
        except Exception as e:
            logging.error(f"Failed to write frame performance to log: {e}")

    def change_detector_model(self, model_name):
        """Changes the active pose detector model. Can only be done when stopped."""
        if self.state not in [AppState.STOPPED, AppState.READY]:
            logging.warning(f"Cannot change detector model while in state {self.state.name}. Please stop first.")
            if self.gui:
                # Revert the dropdown in the GUI to the actual current model
                self.gui.selected_detector.set(self.config['detector_model'])
            return

        if model_name == self.config['detector_model']:
            logging.info(f"Detector model '{model_name}' is already active.")
            return

        logging.info(f"Changing detector model to: {model_name}")
        self.update_config('detector_model', model_name)

        # Log the change event which will also reset the new model's stats
        self._log_perf_event()

        self._initialize_detector()
        # Save the new landmark map for the new model
        self.pose_detector.save_landmark_map_to_csv()

    def start_all(self):
        """Starts NDI, OSC, and the video stream in order."""
        logging.info("Starting all services (NDI, OSC, Video)...")
        self.start_ndi()
        self.start_osc()
        self.start() # This will change state to RUNNING

    def start(self):
        if self.state == AppState.RUNNING:
            logging.warning("Start command issued, but already running.")
            return

        # Simply update the state. The run() loop will handle resource creation.
        self.frame_count = 0
        self.update_state(AppState.RUNNING)

    def stop(self):
        logging.info("Stopping all services (Video, NDI, OSC)...")
        # The run() loop will see the state change and release resources.
        self.update_state(AppState.STOPPED)

        # As a safety measure, also stop the outputs when master stop is called
        self.stop_osc()
        self.stop_ndi()

    def stop_video_stream(self):
        """Stops only the video stream, leaving NDI/OSC active."""
        if self.state in [AppState.STOPPED, AppState.READY]:
            logging.warning("Stop video stream command issued, but already stopped.")
            return
        logging.info("Stopping video stream only...")
        self.update_state(AppState.STOPPED)

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
                        if self.gui:
                            self.gui.clear_video_info()
                        continue
                    else: # Successfully opened
                        width = int(self.video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(self.video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        self.video_width = width
                        self.video_height = height
                        if self.gui:
                            self.gui.update_video_info(width, height)
                        
                        # Log the start event now that we have the resolution
                        self._log_perf_event()
                            
                start_time = time.perf_counter()

                frame = self.capture_frame()
                if frame is not None:
                    self.frame_count += 1
                    # Print on the first frame and then roughly once per second
                    if self.frame_count == 1 or self.frame_count % self.config['fps_limit'] == 0:
                        logging.debug(f"Processing frame: {self.frame_count}")

                    # --- Start Performance Timing ---
                    processing_start_time = time.perf_counter()

                    # 1. Process the image to find landmarks (core model performance)
                    self.pose_detector.process_image(frame)

                    # 2. Conditionally draw landmarks on the original frame for NDI output
                    if self.config['draw_ndi_overlay']:
                        self.pose_detector.draw_landmarks(frame)
                    
                    # --- End Performance Timing ---
                    processing_end_time = time.perf_counter()

                    # --- Log Performance Data for the core work ---
                    self._log_perf_frame(processing_end_time - processing_start_time)

                    # Send landmarks via OSC AFTER processing the frame
                    if self.osc_active:
                        self.pose_detector.send_landmarks_via_osc(self.osc_client, self.frame_count, self.config['fps_limit'])

                    # --- Prepare the preview frame (outside of performance timing) ---
                    # The preview frame always gets an overlay.
                    preview_frame = frame.copy()
                    if not self.config['draw_ndi_overlay']:
                        # If the overlay wasn't drawn for NDI, draw it now for the preview.
                        self.pose_detector.draw_landmarks(preview_frame)

                    # Put preview frame in queue
                    try:
                        self.preview_frame_queue.put_nowait(preview_frame)
                    except queue.Full:
                        pass # GUI is lagging, just drop the frame
                    
                    # Send the (conditionally modified) frame to NDI
                    self.send_video_via_ndi(frame)
                else:
                    # This is a normal end-of-stream event.
                    logging.info("End of video stream. Stopping video stream.")
                    self.stop_video_stream()
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
                    self.video_width = 0
                    self.video_height = 0
                    if self.gui:
                        self.gui.clear_video_info()
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