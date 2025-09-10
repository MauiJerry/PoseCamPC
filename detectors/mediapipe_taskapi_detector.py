# detectors/mediapipe_task_detector.py

from __future__ import annotations
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.framework.formats import landmark_pb2
import numpy as np
import cv2
import threading
import os
import time
import logging

from .abstract_pose_detector import AbstractPoseDetector

# Define some model paths for convenience
DEFAULT_MODEL = 'pose_landmarker_full.task'
MODELS = {
    'lite': 'pose_landmarker_lite.task',
    'full': 'pose_landmarker_full.task',
    'heavy': 'pose_landmarker_heavy.task',
}

class PoseDetectorMediaPipeTask(AbstractPoseDetector):
    """
    MediaPipe Pose Detector implementation using the modern Task API.
    This version is more configurable and supports features like segmentation masks.
    """
    def __init__(self, model: str = 'full', num_poses: int = 1, output_segmentation: bool = False):
        super().__init__()
        
        # --- Configuration Options ---
        self._model_key = model
        self.num_poses = num_poses
        self.min_pose_detection_confidence = 0.5
        self.min_pose_presence_confidence = 0.5
        self.min_tracking_confidence = 0.5
        self.output_segmentation_masks = output_segmentation
        
        # Determine the model file path
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_cache_dir = os.path.join(base_dir, 'model_cache')
        os.makedirs(model_cache_dir, exist_ok=True)
        self._model_path = os.path.join(model_cache_dir, MODELS.get(model, DEFAULT_MODEL))

        # --- Instance variables for the Task API ---
        self._landmarker: vision.PoseLandmarker | None = None
        self._lock = threading.Lock()
        self._latest_result: vision.PoseLandmarkerResult | None = None
        self._latest_timestamp_ms = 0
        
        self.model_name = f"MediaPipe Task ({self._model_key})"
        # The landmark map is the same as the legacy API, which is convenient
        self.pose_id_to_name = {lm.value: lm.name.lower() for lm in mp.solutions.pose.PoseLandmark}
        
        self._create_landmarker()

    def _create_landmarker(self):
        """Creates or re-creates the PoseLandmarker instance with current settings."""
        logging.info(f"Creating PoseLandmarker with model: {self._model_path}")
        try:
            base_options = python.BaseOptions(model_asset_path=self._model_path)
            options = vision.PoseLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.LIVE_STREAM,
                num_poses=self.num_poses,
                min_pose_detection_confidence=self.min_pose_detection_confidence,
                min_pose_presence_confidence=self.min_pose_presence_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
                output_segmentation_masks=self.output_segmentation_masks,
                result_callback=self._result_callback
            )
            # Close existing landmarker before creating a new one
            if self._landmarker:
                self._landmarker.close()
            self._landmarker = vision.PoseLandmarker.create_from_options(options)
            logging.info("PoseLandmarker created successfully.")
        except Exception as e:
            logging.error(f"Failed to create PoseLandmarker: {e}")
            self._landmarker = None

    def _result_callback(self, result: vision.PoseLandmarkerResult, output_image: mp.Image, timestamp_ms: int):
        """Asynchronous callback to receive detection results."""
        with self._lock:
            self._latest_result = result
            self._latest_timestamp_ms = timestamp_ms

    def process_image(self, image):
        """Triggers asynchronous detection and formats the latest available result."""
        if not self._landmarker:
            self.latest_landmarks = []
            return None

        self.image_height, self.image_width, _ = image.shape
        
        # MediaPipe expects RGB images.
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
        
        # Trigger async detection. The result will be sent to _result_callback.
        current_timestamp_ms = int(time.time() * 1000)
        self._landmarker.detect_async(mp_image, current_timestamp_ms)
        
        # --- Retrieve and format the latest result ---
        self.latest_landmarks = []
        with self._lock:
            result = self._latest_result # Make a local copy to work with
            self.latest_results = result # Store raw result for drawing
            
        if result and result.pose_landmarks:
            for person_landmarks in result.pose_landmarks:
                skeleton = [
                    (lm.x, lm.y, lm.z, lm.visibility) for lm in person_landmarks
                ]
                self.latest_landmarks.append(skeleton)
        
        return result

    def draw_landmarks(self, frame):
        """Draws the pose landmarks and optional segmentation mask on the frame."""
        if not self.latest_results or not self.latest_results.pose_landmarks:
            return

        # Create a mutable copy for drawing
        annotated_image = frame.copy()

        # --- 1. Draw Segmentation Mask (if available) ---
        if self.output_segmentation_masks and self.latest_results.segmentation_masks:
            for mask in self.latest_results.segmentation_masks:
                mask_array = mask.numpy_view()
                # Create a solid color mask and blend it
                colored_mask = np.zeros_like(annotated_image, dtype=np.uint8)
                colored_mask[:] = (0, 200, 0) # Green color for the mask
                # Apply the mask
                condition = np.stack((mask_array,) * 3, axis=-1) > 0.1
                annotated_image = np.where(condition, cv2.addWeighted(annotated_image, 0.3, colored_mask, 0.7, 0), annotated_image)

        # --- 2. Draw Pose Landmarks on top ---
        for person_landmarks in self.latest_results.pose_landmarks:
            pose_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
            pose_landmarks_proto.landmark.extend([
                landmark_pb2.NormalizedLandmark(x=lm.x, y=lm.y, z=lm.z) for lm in person_landmarks
            ])
            mp.solutions.drawing_utils.draw_landmarks(
                annotated_image,
                pose_landmarks_proto,
                mp.solutions.pose.POSE_CONNECTIONS,
                mp.solutions.drawing_styles.get_default_pose_landmarks_style()
            )
        
        # Copy the annotated image data back to the original frame
        frame[:] = annotated_image[:]

    # --- Accessors to change settings at runtime ---
    
    def set_num_poses(self, num_poses: int):
        """Updates the number of poses and recreates the landmarker."""
        if self.num_poses != num_poses:
            self.num_poses = num_poses
            self._create_landmarker() # Re-initialize with new setting
            
    def set_model(self, model_key: str):
        """Updates the model and recreates the landmarker."""
        if self._model_key != model_key and model_key in MODELS:
            self._model_key = model_key
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            model_cache_dir = os.path.join(base_dir, 'model_cache')
            self._model_path = os.path.join(model_cache_dir, MODELS[model_key])
            self._create_landmarker()

    def set_output_segmentation(self, enabled: bool):
        """Enables or disables segmentation masks and recreates the landmarker."""
        if self.output_segmentation_masks != enabled:
            self.output_segmentation_masks = enabled
            self._create_landmarker()
	

