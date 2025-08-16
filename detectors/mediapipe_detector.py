from mediapipe import solutions as mp
from .abstract_pose_detector import AbstractPoseDetector

class PoseDetectorMediapipe(AbstractPoseDetector):
    # Copied from old detector for legacy OSC mode
    pose_id_to_name = {
        0: 'head', 1: 'mp_eye_inner_l', 2: 'eye_l', 3: 'mp_eye_outer_l',
        4: 'mp_eye_inner_r', 5: 'eye_r', 6: 'mp_eye_outer_r', 7: 'mp_ear_l',
        8: 'mp_ear_r', 9: 'mp_mouth_l', 10: 'mp_mouth_r', 11: 'shoulder_l',
        12: 'shoulder_r', 13: 'elbow_l', 14: 'elbow_r', 15: 'wrist_l',
        16: 'wrist_r', 17: 'mp_pinky_l', 18: 'mp_pinky_r', 19: 'handtip_l',
        20: 'handtip_r', 21: 'thumb_l', 22: 'thumb_r', 23: 'hip_l',
        24: 'hip_r', 25: 'knee_l', 26: 'knee_r', 27: 'ankle_l',
        28: 'ankle_r', 29: 'mp_heel_l', 30: 'mp_heel_r', 31: 'foot_l',
        32: 'foot_r'
    }

    def __init__(self):
        super().__init__()
        self.mp_pose = mp.pose
        self.pose = self.mp_pose.Pose()
        self.mp_draw = mp.drawing_utils
        self.latest_results = None
        # Add state for legacy OSC mode
        self.frame_count = 0
        self.image_height = 0
        self.image_width = 0

    def process_image(self, image):
        # Update state for legacy OSC
        self.image_height, self.image_width, _ = image.shape
        self.frame_count += 1

        self.latest_results = self.pose.process(image)
        if self.latest_results.pose_landmarks:
            # Wrap the single skeleton in a list to conform to the base class contract
            skeleton = [
                (lm.x, lm.y, lm.z)
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

    # --- Methods for Legacy OSC Mode ---

    def get_landmark_name(self, landmark_id):
        return self.pose_id_to_name.get(landmark_id, "Unknown")

    def send_legacy_landmarks_via_osc(self, osc_client):
        """Sends landmarks using the old method (one message per landmark)."""
        if osc_client is None:
            return

        try:
            # Send metadata
            osc_client.send_message("/framecount", self.frame_count)
            osc_client.send_message(f"/image-height", self.image_height)
            osc_client.send_message(f"/image-width", self.image_width)

            if self.latest_results and self.latest_results.pose_landmarks:
                landmarks = self.latest_results.pose_landmarks.landmark
                for idx, lm in enumerate(landmarks):
                    osc_client.send_message(f"/p1/{self.get_landmark_name(idx)}", [lm.x, lm.y, lm.z])
                osc_client.send_message(f"/numLandmarks", len(landmarks))
        except Exception as e:
            print(f"[OSC-Legacy] Error sending message: {e}")