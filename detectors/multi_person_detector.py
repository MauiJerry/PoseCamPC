from mediapipe import solutions as mp
from .abstract_pose_detector import AbstractPoseDetector

class MultiPersonPoseDetector(AbstractPoseDetector):
    def __init__(self):
        super().__init__()
        self.model_name = "MediaPipe Pose"
        self.mp_pose = mp.pose
        self.pose = self.mp_pose.Pose(enable_segmentation=False, min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.mp_draw = mp.drawing_utils
        self.latest_results = None

    def process_image(self, image):
        self.latest_results = self.pose.process(image)
        if self.latest_results.pose_landmarks:
            # MediaPipe's Pose solution detects one person. Wrap the skeleton in a list
            # to conform to the base class contract for multi-person data structure.
            skeleton = [
                (lm.x, lm.y, lm.z, lm.visibility)
                for lm in self.latest_results.pose_landmarks.landmark
            ]
            self.latest_landmarks = [skeleton]
        else:
            self.latest_landmarks = []
        return self.latest_results

    def draw_landmarks(self, frame):
        # Use the latest results from process_image to avoid reprocessing
        if self.latest_results and self.latest_results.pose_landmarks:
            self.mp_draw.draw_landmarks(frame, self.latest_results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS)
            