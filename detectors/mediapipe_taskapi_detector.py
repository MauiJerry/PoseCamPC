# detectors/mediapipe_task_detector.py

from __future__ import annotations
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.framework.formats import landmark_pb2
import numpy as np
import cv2
import os
import time # Keep for timestamping
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
        self._model_path = self._get_model_path(self._model_key)

        # --- Instance variables for the Task API ---
        self._landmarker: vision.PoseLandmarker | None = None
        
        seg_suffix = " +Seg" if self.output_segmentation_masks else ""
        self.model_name = f"MediaPipe Task ({self._model_key}{seg_suffix})"
        # The landmark map is the same as the legacy API, which is convenient
        self.pose_id_to_name = {lm.value: lm.name.lower() for lm in mp.solutions.pose.PoseLandmark}
        
        self._create_landmarker()

    def _get_model_path(self, model_key: str) -> str:
        """Constructs an absolute path to the model file."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_cache_dir = os.path.join(project_root, 'model_cache')
        model_filename = MODELS.get(model_key, DEFAULT_MODEL)
        return os.path.join(model_cache_dir, model_filename)

    def _create_landmarker(self):
        """Creates or re-creates the PoseLandmarker instance with current settings."""
        logging.info(f"Creating PoseLandmarker with model: {self._model_path}")
        try:
            base_options = python.BaseOptions(model_asset_path=self._model_path)
            options = vision.PoseLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.VIDEO,
                num_poses=self.num_poses,
                min_pose_detection_confidence=self.min_pose_detection_confidence,
                min_pose_presence_confidence=self.min_pose_presence_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
                output_segmentation_masks=self.output_segmentation_masks,
            )
            # Close existing landmarker before creating a new one
            if self._landmarker:
                self._landmarker.close()
            self._landmarker = vision.PoseLandmarker.create_from_options(options)
            logging.info("PoseLandmarker created successfully.")
        except Exception as e:
            # self._model_path is now already absolute
            error_message = (
                f"Failed to create PoseLandmarker: {e}\n"
                "This is likely because the model file is missing.\n"
                f"Please download '{MODELS.get(self._model_key, DEFAULT_MODEL)}' from 'https://developers.google.com/mediapipe/solutions/vision/pose_landmarker/index#models'\n"
                f"and place it in the '{os.path.dirname(self._model_path)}' directory."
            )
            logging.error(error_message)
            raise RuntimeError(error_message) from e

    def process_image(self, image):
        """Triggers asynchronous detection and formats the latest available result."""
        if not self._landmarker:
            self.latest_landmarks = []
            return None

        self.image_height, self.image_width, _ = image.shape
        
        # MediaPipe expects RGB images.
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
        
        # For VIDEO mode, we need a monotonically increasing timestamp.
        timestamp_ms = int(time.monotonic() * 1000)
        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        # --- Retrieve and format the latest result ---
        self.latest_results = result
        self.latest_landmarks = []
        self.latest_bboxes = [] # MediaPipe doesn't provide bboxes, so ensure this is empty
            
        if result and result.pose_landmarks:
            for person_landmarks in result.pose_landmarks:
                skeleton = [
                    (lm.x, lm.y, lm.z, lm.visibility) for lm in person_landmarks
                ]
                self.latest_landmarks.append(skeleton)
        
        return result

    def draw_landmarks(self, frame, draw_bbox: bool, use_native_plot: bool):
        # This detector ignores draw_bbox and use_native_plot as it has no bboxes
        # and its default drawing is already the "native" implementation.
        """Draws the pose landmarks and optional segmentation mask on the frame."""
        if not self.latest_results:
            return

        # --- 1. Draw Segmentation Mask (if available) ---
        if self.output_segmentation_masks and self.latest_results.segmentation_masks:
            # Create a solid green overlay for blending
            green_overlay = np.zeros_like(frame, dtype=np.uint8)
            green_overlay[:] = (0, 200, 0)

            # Combine all masks into a single boolean mask
            combined_mask = np.zeros((self.image_height, self.image_width), dtype=bool)
            for segmentation_mask in self.latest_results.segmentation_masks:
                mask = segmentation_mask.numpy_view() > 0.1
                combined_mask = np.logical_or(combined_mask, mask)

            # Expand mask to 3 channels for blending
            condition = np.stack((combined_mask,) * 3, axis=-1)

            # Create a blended image
            blended = cv2.addWeighted(frame, 0.3, green_overlay, 0.7, 0)

            # Copy the blended pixels onto the original frame only where the mask is true (in-place)
            np.copyto(frame, blended, where=condition)

        # --- 2. Draw Pose Landmarks on top (in-place) ---
        if self.latest_results.pose_landmarks:
            for person_landmarks in self.latest_results.pose_landmarks:
                pose_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
                pose_landmarks_proto.landmark.extend([
                    landmark_pb2.NormalizedLandmark(x=lm.x, y=lm.y, z=lm.z)
                    for lm in person_landmarks
                ])
                mp.solutions.drawing_utils.draw_landmarks(
                    frame,
                    pose_landmarks_proto,
                    mp.solutions.pose.POSE_CONNECTIONS,
                    mp.solutions.drawing_styles.get_default_pose_landmarks_style()
                )

    def has_segmentation(self) -> bool:
        """Returns True if the last processed result contains segmentation data."""
        return bool(self.output_segmentation_masks and self.latest_results and self.latest_results.segmentation_masks)

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
            self._model_path = self._get_model_path(model_key)
            self._create_landmarker()

    def set_output_segmentation(self, enabled: bool):
        """Enables or disables segmentation masks and recreates the landmarker."""
        if self.output_segmentation_masks != enabled:
            self.output_segmentation_masks = enabled
            self._create_landmarker()
	
