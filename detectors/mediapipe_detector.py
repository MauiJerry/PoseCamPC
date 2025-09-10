from mediapipe import solutions as mp
import cv2
from .abstract_pose_detector import AbstractPoseDetector

class PoseDetectorMediapipe(AbstractPoseDetector):
    def __init__(self):
        super().__init__()
        self.model_name = "MediaPipe Pose (Default)"
        self.pose = mp.pose.Pose()
 
        # Override the default mapping with the one from MediaPipe's PoseLandmark enum.
        # This ensures the names are the "source of truth" from the library itself.
        self.pose_id_to_name = {
            landmark.value: landmark.name.lower()
            for landmark in mp.pose.PoseLandmark
        }
 
    def process_image(self, image):
        self.image_height, self.image_width, _ = image.shape

        # MediaPipe expects RGB images, so we need to convert from BGR.
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        self.latest_results = self.pose.process(image_rgb)
        if self.latest_results.pose_landmarks:
            # Wrap the single skeleton in a list to conform to the base class contract
            skeleton = [
                (lm.x, lm.y, lm.z, lm.visibility)
                for lm in self.latest_results.pose_landmarks.landmark
            ]
            self.latest_landmarks = [skeleton]
        else:
            self.latest_landmarks = []

        self.latest_bboxes = [] # MediaPipe doesn't provide bboxes, so ensure this is empty
        return self.latest_results

    def draw_landmarks(self, frame, draw_bbox: bool, use_native_plot: bool):
        # This detector ignores draw_bbox and use_native_plot as it has no bboxes
        # and its default drawing is already the "native" implementation.
        # Use the latest results from process_image to avoid reprocessing
        if self.latest_results and self.latest_results.pose_landmarks:
            mp.drawing_utils.draw_landmarks(frame, self.latest_results.pose_landmarks, mp.pose.POSE_CONNECTIONS)