from abc import ABC, abstractmethod
import logging
import time
from pythonosc import udp_client, osc_bundle_builder, osc_message_builder
import datetime

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
        self._osc_person_bundle_log_count = 0

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

    def send_landmarks_via_osc(self, client: udp_client.SimpleUDPClient, fps_limit: int = 30):
        if not client:
            return

        # The timetag is an instruction for the receiver. IMMEDIATELY means process now.
        timetag = osc_bundle_builder.IMMEDIATELY
        bundle_builder = osc_bundle_builder.OscBundleBuilder(timetag)

        # --- Add metadata messages to the bundle ---

        # 0a. Add a high-resolution Unix timestamp for machine use (the standard).
        # This float value is highly efficient for calculations and is a common standard.
        msg_timestamp = osc_message_builder.OscMessageBuilder(address="/pose/timestamp")
        msg_timestamp.add_arg(time.time())
        bundle_builder.add_content(msg_timestamp.build())

        # 0b. Add a human-readable, machine-parsable timestamp string.
        # Format: yyyy.mm.dd.hh.mm.ss.ms
        now = datetime.datetime.now()
        ts_str = now.strftime("%Y.%m.%d.%H.%M.%S") + f".{now.microsecond // 1000:03d}"
        msg_timestamp_str = osc_message_builder.OscMessageBuilder(address="/pose/timestamp_str")
        msg_timestamp_str.add_arg(ts_str)
        bundle_builder.add_content(msg_timestamp_str.build())

        # 1. Add frame_count and num_persons to every bundle
        msg_frame_count = osc_message_builder.OscMessageBuilder(address="/pose/frame_count")
        msg_frame_count.add_arg(self.frame_count)
        bundle_builder.add_content(msg_frame_count.build())

        msg_num_persons = osc_message_builder.OscMessageBuilder(address="/pose/num_persons")
        msg_num_persons.add_arg(len(self.latest_landmarks))
        bundle_builder.add_content(msg_num_persons.build())

        # 2. Add other metadata periodically (e.g., every second)
        # Send on the first frame, and then every `fps_limit` frames thereafter.
        if fps_limit > 0 and (self.frame_count == 1 or self.frame_count % fps_limit == 0):
            msg_img_w = osc_message_builder.OscMessageBuilder(address="/pose/image_width")
            msg_img_w.add_arg(self.image_width)
            bundle_builder.add_content(msg_img_w.build())

            msg_img_h = osc_message_builder.OscMessageBuilder(address="/pose/image_height")
            msg_img_h.add_arg(self.image_height)
            bundle_builder.add_content(msg_img_h.build())

        # --- Add landmark data ---
        for person_id, skeleton in enumerate(self.latest_landmarks):
            if not skeleton:
                continue
            
            for landmark_id, (x, y, z) in enumerate(skeleton):
                msg = osc_message_builder.OscMessageBuilder(address=f"/pose/p{person_id + 1}/{landmark_id}")
                msg.add_arg(float(x)); msg.add_arg(float(y)); msg.add_arg(float(z))
                bundle_builder.add_content(msg.build())
        
        bundle = bundle_builder.build()

        # Log the first 2 bundles, and the first 2 bundles with person data.
        has_person = len(self.latest_landmarks) > 0
        should_log = False
        log_reason_parts = []

        # Condition 1: Log the first two bundles unconditionally
        if self._osc_bundle_log_count < 2:
            should_log = True
            log_reason_parts.append(f"Overall Log #{self._osc_bundle_log_count + 1}")

        # Condition 2: Log the first two bundles that contain person data
        if has_person and self._osc_person_bundle_log_count < 2:
            if not should_log:
                should_log = True
            log_reason_parts.append(f"Person Data Log #{self._osc_person_bundle_log_count + 1}")

        if should_log:
            log_reason = " | ".join(log_reason_parts)
            logging.info(f"--- OSC Bundle Sent ({log_reason}) ---")
            # The timetag is a property of the bundle itself. 1 means "IMMEDIATELY".
            timetag_info = f" (1 = IMMEDIATE)" if timetag == 1 else ""
            logging.info(f"  Timetag: {timetag}{timetag_info}")
            for msg in bundle:
                # Round float args for cleaner logging, but leave other types (like strings) as-is.
                rounded_args = [round(p, 4) if isinstance(p, float) else p for p in msg.params]
                logging.info(f"  Address: {msg.address}, Args: {rounded_args}")
            logging.info("-------------------------------------------------")

            # Increment counters after logging
            if self._osc_bundle_log_count < 2:
                self._osc_bundle_log_count += 1
            if has_person and self._osc_person_bundle_log_count < 2:
                self._osc_person_bundle_log_count += 1

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