import cv2
import os
from ultralytics import YOLO
from .abstract_pose_detector import AbstractPoseDetector

# CAVEAT: running two YOLO models per frame is computationally expensive
# it gets 
# Define the connections between COCO keypoints for drawing the skeleton
COCO17_EDGES = [
    (5, 7), (7, 9), (6, 8), (8, 10),
    (11, 13), (13, 15), (12, 14), (14, 16),
    (5, 6), (11, 12), (5, 11), (6, 12),
    (0, 1), (0, 2), (1, 3), (2, 4),
]

class PoseDetectorYOLO_Seg(AbstractPoseDetector):
    """
    A YOLO-based detector that performs both pose estimation and instance segmentation.
    It runs two models in two passes on each frame.
    """
    def __init__(self, pose_model_filename='yolov8n-pose.pt', seg_model_filename='yolov8n-seg.pt'):
        super().__init__()

        # --- Model Loading ---
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_cache_dir = os.path.join(base_dir, 'model_cache')
        os.makedirs(model_cache_dir, exist_ok=True)

        full_pose_model_path = os.path.join(model_cache_dir, pose_model_filename)
        full_seg_model_path = os.path.join(model_cache_dir, seg_model_filename)

        self.pose_model = YOLO(full_pose_model_path)
        self.seg_model = YOLO(full_seg_model_path)

        # --- Override instance variables ---
        self.model_name = "YOLOv8 Pose+Seg"

        # The primary landmark map is from the pose model
        self.pose_id_to_name = {
            0: 'nose', 1: 'eye_l', 2: 'eye_r', 3: 'ear_l', 4: 'ear_r',
            5: 'shoulder_l', 6: 'shoulder_r', 7: 'elbow_l', 8: 'elbow_r',
            9: 'wrist_l', 10: 'wrist_r', 11: 'hip_l', 12: 'hip_r',
            13: 'knee_l', 14: 'knee_r', 15: 'ankle_l', 16: 'ankle_r'
        }
        print(f"PoseDetectorYOLO_Seg initialized with models: {pose_model_filename}, {seg_model_filename}")

    def process_image(self, image):
        self.image_height, self.image_width, _ = image.shape

        # --- Two-pass processing ---
        # 1. Pose detection
        pose_results = self.pose_model(image, verbose=False)
        # 2. Segmentation (filtered for 'person' class only)
        seg_results = self.seg_model(image, verbose=False, classes=[0])

        # Store both raw results in a tuple
        self.latest_results = (pose_results, seg_results)

        # --- Process pose results for landmarks (same as YOLO_G) ---
        self.latest_landmarks = []
        for person_result in pose_results:
            if person_result.keypoints and person_result.keypoints.xy.shape[1] > 0:
                norm_coords = person_result.keypoints.xyn[0]
                confidences = person_result.keypoints.conf[0]
                skeleton = []
                for i in range(len(norm_coords)):
                    x, y = norm_coords[i]
                    visibility = confidences[i]
                    z = 0.0
                    skeleton.append((float(x), float(y), z, float(visibility)))
                self.latest_landmarks.append(skeleton)

        return self.latest_results

    def draw_landmarks(self, frame):
        if not self.latest_results:
            return

        _, seg_results = self.latest_results

        # --- Draw Segmentation First ---
        # The plot() method returns a new frame with masks, which we use as a base.
        if seg_results and seg_results[0].masks:
            frame_with_masks = seg_results[0].plot(boxes=False, labels=False)
            frame[:] = frame_with_masks[:] # Copy pixel data to our input frame

        # --- Draw Pose Skeletons on Top (using efficient in-place drawing) ---
        if not self.latest_landmarks:
            return

        h, w, _ = frame.shape
        for skeleton in self.latest_landmarks:
            pixel_coords = [(int(nx * w), int(ny * h)) if v > 0.1 else None for nx, ny, _, v in skeleton]

            for start_idx, end_idx in COCO17_EDGES:
                if start_idx < len(pixel_coords) and end_idx < len(pixel_coords) and pixel_coords[start_idx] and pixel_coords[end_idx]:
                    cv2.line(frame, pixel_coords[start_idx], pixel_coords[end_idx], (255, 255, 255), 1)
            
            for px_coord in pixel_coords:
                if px_coord:
                    cv2.circle(frame, px_coord, 3, (0, 255, 0), -1)