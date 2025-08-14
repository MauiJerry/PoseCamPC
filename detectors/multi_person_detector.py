from mediapipe import solutions as mp
from detectors.base import AbstractPoseDetector

class MultiPersonPoseDetector(AbstractPoseDetector):
    def __init__(self):
        super().__init__()
        self.mp_pose = mp.pose
        self.pose = self.mp_pose.Pose(enable_segmentation=False, min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.mp_draw = mp.drawing_utils
        self.multi_person = True  # Just a flag for potential future conditional UI/logic

    def process_image(self, image):
        results = self.pose.process(image)
        if results.pose_landmarks:
            self.latest_landmarks = [
                (lm.x, lm.y, lm.z)
                for lm in results.pose_landmarks.landmark
            ]
        else:
            self.latest_landmarks = []
        return results

    def draw_landmarks(self, frame):
        results = self.pose.process(frame)
        if results.pose_landmarks:
            self.mp_draw.draw_landmarks(frame, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS)
            