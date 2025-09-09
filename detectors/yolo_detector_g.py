# In yolo_detector.py, gemini version

import cv2
import os
from ultralytics import YOLO
from .abstract_pose_detector import AbstractPoseDetector

class PoseDetectorYOLO_G(AbstractPoseDetector):
    def __init__(self, model_filename='yolov8n-pose.pt'):
        """
        Initializes the YOLO Pose Detector.
        Args:
            model_filename (str): The name of the YOLO pose model file (e.g., 'yolov8n-pose.pt').
                                  The model will be downloaded to a local 'model_cache' directory.
        """
        super().__init__()
        
        # Define the cache directory relative to the project root
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_cache_dir = os.path.join(base_dir, 'model_cache')
        os.makedirs(model_cache_dir, exist_ok=True)
        
        # Construct the full path. Ultralytics will download to this path if the file doesn't exist.
        full_model_path = os.path.join(model_cache_dir, model_filename)
        
        # Instantiate the YOLO model
        self.model = YOLO(full_model_path)
        
        # --- Override instance variables from the abstract class ---
        
        # 1. Set the model name for OSC metadata
        self.model_name = f"YOLOv8 ({model_filename})"

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
        
        # Reset landmarks from the previous frame
        self.latest_landmarks = []

        # The result object contains detections for all people in the frame
        for person_result in self.latest_results:
            # Check if any keypoints were detected for this person
            if person_result.keypoints and person_result.keypoints.xy.shape[1] > 0:
                # Get normalized coordinates and confidence scores
                norm_coords = person_result.keypoints.xyn[0]
                confidences = person_result.keypoints.conf[0]
                
                skeleton = []
                for i in range(len(norm_coords)):
                    # Get the (x, y) coordinates
                    x, y = norm_coords[i]
                    
                    # Get the confidence score, which we'll use for visibility
                    visibility = confidences[i]
                    
                    # YOLO does not provide a Z-coordinate, so we'll use 0.0 as a placeholder.
                    # This keeps the data structure consistent with the abstract class.
                    z = 0.0
                    
                    skeleton.append((float(x), float(y), z, float(visibility)))
                
                self.latest_landmarks.append(skeleton)

        return self.latest_results

    def draw_landmarks(self, frame):
        """
        Draws the detected pose landmarks and connections on the given frame.
        """
        # The ultralytics results object has a built-in plot() method which is very convenient.
        # It handles drawing boxes, keypoints, and connections.
        if self.latest_results:
            # The plot() method returns a new image with annotations.
            # We need to overwrite the original frame with the annotated one.
            # Note: This assumes only one result object, which is typical for single-image processing.
            annotated_frame = self.latest_results[0].plot()
            # To modify the frame in-place, copy the annotated data back
            frame[:] = annotated_frame[:]