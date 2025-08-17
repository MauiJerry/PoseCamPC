from abc import ABC, abstractmethod
import logging
from pythonosc import udp_client, osc_bundle_builder, osc_message_builder

class AbstractPoseDetector(ABC):
    # This mapping is the single source of truth for converting landmark IDs to names.
    # It is used by the legacy OSC mode and documented in the README for the bundle mode.
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
        """
        Initializes the detector.
        self.latest_landmarks is now a list of skeletons, where each skeleton is a list of landmarks.
        e.g., [ [(x1,y1,z1), (x2,y2,z2), ...], [(x1,y1,z1), ...] ]
        """
        self.latest_landmarks = []
        self.latest_results = None # To store the raw results from the backend
        self._osc_bundle_log_count = 0

        # State for legacy OSC mode
        self.frame_count = 0
        self.image_height = 0
        self.image_width = 0

    @abstractmethod
    def process_image(self, image):
        pass

    @abstractmethod
    def draw_landmarks(self, frame):
        pass

    def send_landmarks_via_osc(self, client: udp_client.SimpleUDPClient):
        if not client or not self.latest_landmarks:
            return

        bundle_builder = osc_bundle_builder.OscBundleBuilder(osc_bundle_builder.IMMEDIATELY)

        for person_id, skeleton in enumerate(self.latest_landmarks):
            if not skeleton:
                continue
            
            for landmark_id, (x, y, z) in enumerate(skeleton):
                msg = osc_message_builder.OscMessageBuilder(address=f"/pose/p{person_id + 1}/{landmark_id}")
                msg.add_arg(float(x)); msg.add_arg(float(y)); msg.add_arg(float(z))
                bundle_builder.add_content(msg.build())
        
        bundle = bundle_builder.build()

        # Log the contents of the first two bundles for debugging purposes
        if self._osc_bundle_log_count < 2:
            logging.info(f"--- OSC Bundle Sent (Log #{self._osc_bundle_log_count + 1}) ---")
            # The bundle is an iterable of the messages it contains
            for msg in bundle:
                # Round the float args for cleaner logging
                rounded_args = [round(p, 4) for p in msg.params]
                logging.info(f"  Address: {msg.address}, Args: {rounded_args}")
            logging.info("-------------------------------------------------")
            self._osc_bundle_log_count += 1

        try:
            client.send(bundle)
        except Exception as e:
            print(f"[OSC] Error sending landmark bundle: {e}")

    # --- Methods for Legacy OSC Mode ---

    def get_landmark_name(self, landmark_id):
        """Looks up the landmark name from the class's mapping dictionary."""
        return self.pose_id_to_name.get(landmark_id, "Unknown")

    def send_legacy_landmarks_via_osc(self, osc_client):
        """Sends landmarks using the legacy method (one message per landmark)."""
        if osc_client is None:
            return

        try:
            # Send metadata
            osc_client.send_message("/framecount", self.frame_count)
            osc_client.send_message(f"/image-height", self.image_height)
            osc_client.send_message(f"/image-width", self.image_width)

            # Legacy mode only supports one person (the first skeleton)
            if self.latest_landmarks and self.latest_landmarks[0]:
                skeleton = self.latest_landmarks[0]
                for idx, (x, y, z) in enumerate(skeleton):
                    osc_client.send_message(f"/p1/{self.get_landmark_name(idx)}", [float(x), float(y), float(z)])
                osc_client.send_message(f"/numLandmarks", len(skeleton))
        except Exception as e:
            print(f"[OSC-Legacy] Error sending message: {e}")