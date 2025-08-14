from mediapipe import solutions as mp
from .base import AbstractPoseDetector

class PoseDetectorMediapipe(AbstractPoseDetector):
    def __init__(self):
        super().__init__()
        self.mp_pose = mp.pose
        self.pose = self.mp_pose.Pose()
        self.mp_draw = mp.drawing_utils

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
            