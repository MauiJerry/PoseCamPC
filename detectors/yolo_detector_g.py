# In yolo_detector.py, gemini version

import logging
import cv2
import os
from ultralytics import YOLO
from .abstract_pose_detector import AbstractPoseDetector

# Define the connections between COCO keypoints for drawing the skeleton
COCO17_EDGES = [
    (5, 7), (7, 9), (6, 8), (8, 10),
    (11, 13), (13, 15), (12, 14), (14, 16),
    (5, 6), (11, 12), (5, 11), (6, 12),
    (0, 1), (0, 2), (1, 3), (2, 4),
]

class PoseDetectorYOLO_G(AbstractPoseDetector):
    def __init__(self, model_filename='yolov8n-pose.pt', display_name=None):
        """
        Initializes the YOLO Pose Detector.
        Args:
            model_filename (str): The name of the YOLO pose model file (e.g., 'yolov8n-pose.pt').
                                  The model will be downloaded to a local 'model_cache' directory.
            display_name (str, optional): A name for the model to be used in logs and OSC.
        """
        super().__init__()

        # Construct an absolute path to the model cache directory relative to this script file
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_cache_dir = os.path.join(project_root, 'model_cache')
        model_path = os.path.join(model_cache_dir, model_filename)

        if not os.path.exists(model_path):
            # --- Add diagnostic logging ---
            dir_contents = "Directory does not exist."
            if os.path.isdir(model_cache_dir):
                dir_contents = "\n".join(os.listdir(model_cache_dir))
                if not dir_contents:
                    dir_contents = "<Directory is empty>"
            
            error_message = (
                f"YOLO model file not found at: {model_path}\n"
                f"\nContents of '{model_cache_dir}':\n---\n{dir_contents}\n---\n"
                f"Please download '{model_filename}' manually and place it in the '{model_cache_dir}' directory.\n"
                "You can find official models on the Ultralytics GitHub releases page."
            )
            logging.error(error_message)
            raise FileNotFoundError(error_message)

        # Instantiate the YOLO model
        try:
            self.model = YOLO(model_path)
        except Exception as e:
            error_message = (
                f"Failed to load YOLO model from path: {model_path}\n"
                f"Error: {e}\n"
                "The file may be corrupt. Try deleting it and downloading it again."
            )
            logging.error(error_message)
            raise RuntimeError(error_message) from e
        
        # --- Override instance variables from the abstract class ---
        
        # 1. Set the model name for OSC metadata
        if display_name:
            self.model_name = display_name
        else:
            # Fallback for backward compatibility or direct instantiation
            self.model_name = f"YOLO ({model_filename})"

        # 2. Define the landmark mapping for YOLO (COCO keypoints)
        # This is crucial for downstream applications to understand the data.
        self.pose_id_to_name = {
            0: 'nose', 1: 'eye_l', 2: 'eye_r', 3: 'ear_l', 4: 'ear_r',
            5: 'shoulder_l', 6: 'shoulder_r', 7: 'elbow_l', 8: 'elbow_r',
            9: 'wrist_l', 10: 'wrist_r', 11: 'hip_l', 12: 'hip_r',
            13: 'knee_l', 14: 'knee_r', 15: 'ankle_l', 16: 'ankle_r'
        }        
        print(f"PoseDetectorYOLO_G initialized with model: {self.model_name}")

    def process_image(self, image):
        """
        Processes an image to detect poses using YOLO.
        Populates self.latest_landmarks with the detected skeletons.
        """
        # Store image dimensions for use in drawing and OSC messages
        self.image_height, self.image_width, _ = image.shape

        # Run pose detection
        # verbose=False prevents it from printing results to the console
        self.latest_results = self.model(image, verbose=False)
        
        self.latest_landmarks = []
        self.latest_bboxes = []

        # The result object is a list, but for a single image it has one element.
        if not self.latest_results:
            return None
        
        result = self.latest_results[0] # Get the Results object for the single image

        # Check if the model detected any keypoints at all
        if result.keypoints and hasattr(result.keypoints, 'xyn'):
            # keypoints.xyn is a tensor of shape (num_persons, num_keypoints, 2)
            all_norm_coords = result.keypoints.xyn
            all_confidences = result.keypoints.conf

            # Get bounding boxes if they exist
            all_bboxes = None
            if result.boxes and hasattr(result.boxes, 'xywhn'):
                all_bboxes = result.boxes.xywhn

            # Iterate through each detected person
            for person_idx in range(len(all_norm_coords)):
                norm_coords = all_norm_coords[person_idx] # Keypoints for one person
                confidences = all_confidences[person_idx] # Confidences for one person

                skeleton = []
                for i in range(len(norm_coords)):
                    x, y = norm_coords[i]
                    visibility = confidences[i]
                    z = 0.0 # YOLO is 2D, so Z is a placeholder
                    skeleton.append((float(x), float(y), z, float(visibility)))
                
                self.latest_landmarks.append(skeleton)

                # Add corresponding bounding box
                if all_bboxes is not None and person_idx < len(all_bboxes):
                    x, y, w, h = all_bboxes[person_idx]
                    self.latest_bboxes.append((float(x), float(y), float(w), float(h)))

        return self.latest_results

    def draw_landmarks(self, frame, draw_bbox: bool, use_native_plot: bool):
        """
        Draws the detected pose landmarks and connections on the given frame.
        """
        if use_native_plot:
            if self.latest_results:
                # The plot() method returns a new image with annotations (skeletons and bboxes).
                annotated_frame = self.latest_results[0].plot()
                # To modify the frame in-place, copy the annotated data back
                frame[:] = annotated_frame[:]
            return

        # --- Manual Drawing using OpenCV ---
        h, w, _ = frame.shape

        # Draw bounding boxes if requested
        if draw_bbox:
            for i, (cx, cy, bw, bh) in enumerate(self.latest_bboxes):
                x1 = int((cx - bw / 2) * w)
                y1 = int((cy - bh / 2) * h)
                x2 = int((cx + bw / 2) * w)
                y2 = int((cy + bh / 2) * h)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 1)

        # Draw skeletons
        for skeleton in self.latest_landmarks:
            # Create a list of pixel coordinates for the current skeleton
            pixel_coords = [(int(nx * w), int(ny * h)) if v > 0.1 else None for nx, ny, _, v in skeleton]

            # Draw keypoints
            for px_coord in pixel_coords:
                if px_coord:
                    cv2.circle(frame, px_coord, 3, (0, 255, 0), -1)

            # Draw the skeleton connections
            for start_idx, end_idx in COCO17_EDGES:
                if start_idx < len(pixel_coords) and end_idx < len(pixel_coords) and pixel_coords[start_idx] and pixel_coords[end_idx]:
                    cv2.line(frame, pixel_coords[start_idx], pixel_coords[end_idx], (255, 255, 255), 1)