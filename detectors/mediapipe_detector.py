from mediapipe import solutions as mp
from .abstract_pose_detector import AbstractPoseDetector

class PoseDetectorMediapipe(AbstractPoseDetector):
    def __init__(self):
        super().__init__()
        self.model_name = "MediaPipe Pose"
        self.pose = mp.pose.Pose()
 
        # Override the default mapping with the one from MediaPipe's PoseLandmark enum.
        # This ensures the names are the "source of truth" from the library itself.
        self.pose_id_to_name = {
            landmark.value: landmark.name.lower()
            for landmark in mp.pose.PoseLandmark
        }
 
    def process_image(self, image):
        # Update state for legacy OSC
        self.image_height, self.image_width, _ = image.shape

        self.latest_results = self.pose.process(image)
        if self.latest_results.pose_landmarks:
            # Wrap the single skeleton in a list to conform to the base class contract
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
        # print("in mediapipe, draw landmarks")
        if self.latest_results and self.latest_results.pose_landmarks:
            mp.drawing_utils.draw_landmarks(frame, self.latest_results.pose_landmarks, mp.pose.POSE_CONNECTIONS)