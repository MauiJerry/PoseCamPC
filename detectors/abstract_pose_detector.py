from abc import ABC, abstractmethod
import logging
import time
from pythonosc import udp_client, osc_bundle_builder, osc_message_builder
import csv
import datetime

class AbstractPoseDetector(ABC):
    # # This mapping is the single source of truth for converting landmark IDs to names.
    # # It is used by the legacy OSC mode and documented in the README for the bundle mode.
    # pose_id_to_name = {
    #     0: 'head', 1: 'mp_eye_inner_l', 2: 'eye_l', 3: 'mp_eye_outer_l',
    #     4: 'mp_eye_inner_r', 5: 'eye_r', 6: 'mp_eye_outer_r', 7: 'mp_ear_l',
    #     8: 'mp_ear_r', 9: 'mp_mouth_l', 10: 'mp_mouth_r', 11: 'shoulder_l',
    #     12: 'shoulder_r', 13: 'elbow_l', 14: 'elbow_r', 15: 'wrist_l',
    #     16: 'wrist_r', 17: 'mp_pinky_l', 18: 'mp_pinky_r', 19: 'handtip_l',
    #     20: 'handtip_r', 21: 'thumb_l', 22: 'thumb_r', 23: 'hip_l',
    #     24: 'hip_r', 25: 'knee_l', 26: 'knee_r', 27: 'ankle_l',
    #     28: 'ankle_r', 29: 'mp_heel_l', 30: 'mp_heel_r', 31: 'foot_l',
    #     32: 'foot_r'
    # }
    

    def __init__(self):
        """
        Initializes the detector.
        self.latest_landmarks is now a list of skeletons, where each skeleton is a list of landmarks.
        e.g., [ [(x1,y1,z1), (x2,y2,z2), ...], [(x1,y1,z1), ...] ]
        defines the pose_id_to_name as instance variable so concrete classes can over ride if desired
        """
        self.pose_id_to_name = {
            0: 'nose', 1: 'eye_inner_l', 2: 'eye_l', 3: 'eye_outer_l',
            4: 'eye_inner_r', 5: 'eye_r', 6: 'eye_outer_r', 7: 'ear_l',
            8: 'ear_r', 9: 'mouth_l', 10: 'mouth_r', 11: 'shoulder_l',
            12: 'shoulder_r', 13: 'elbow_l', 14: 'elbow_r', 15: 'wrist_l',
            16: 'wrist_r', 17: 'pinky_l', 18: 'pinky_r', 19: 'handtip_l',
            20: 'handtip_r', 21: 'thumb_l', 22: 'thumb_r', 23: 'hip_l',
            24: 'hip_r', 25: 'knee_l', 26: 'knee_r', 27: 'ankle_l',
            28: 'ankle_r', 29: 'heel_l', 30: 'heel_r', 31: 'foot_l',
            32: 'foot_r'
        }
        self.model_name = "AbstractDetector"
        # A list of skeletons, where each skeleton is a list of (x, y, z) tuples
        self.latest_landmarks = []
        # A list of bounding boxes, where each bbox is a (x, y, w, h) tuple in normalized coords
        self.latest_bboxes = []
        self.latest_results = None # To store the raw results from the backend
        self._osc_bundle_log_count = 0
        self._osc_person_bundle_log_count = 0
        self.image_height = 0
        self.image_width = 0
        print("AbstractPoseDetector initialized.")

    @abstractmethod
    def process_image(self, image):
        pass

    @abstractmethod
    def draw_landmarks(self, frame, draw_bbox: bool, use_native_plot: bool):
        pass

    def has_segmentation(self) -> bool:
        """Returns True if the last processed result contains segmentation data."""
        return False

    def save_landmark_map_to_csv(self, filename="landmark_idname.csv"):
        """Saves the current landmark ID-to-name mapping to a CSV file."""
        if not self.pose_id_to_name:
            logging.warning("No landmark name map available to save.")
            return

        try:
            # Ensure the names are written in the correct order of their IDs
            sorted_items = sorted(self.pose_id_to_name.items())
            
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['id', 'name'])  # Write header
                for landmark_id, landmark_name in sorted_items:
                    writer.writerow([landmark_id, landmark_name])
            
            logging.info(f"Landmark ID-to-name map successfully saved to {filename}")
        except Exception as e:
            logging.error(f"Failed to save landmark map to {filename}: {e}")

    def send_landmarks_via_osc(self, client: udp_client.SimpleUDPClient, frame_count: int, fps_limit: int = 30):
        if not client:
            return
        bundleStats_metaCount = 0
        bundleStats_personCount = 0
        bundleStats_totalMessages = 0
        bundleStats_numLandmarks = 0

        # The timetag is an instruction for the receiver. IMMEDIATELY means process now.
        timetag = osc_bundle_builder.IMMEDIATELY
        bundle_builder = osc_bundle_builder.OscBundleBuilder(timetag)

        # --- Add metadata messages to the bundle ---

        # 0a. Add a high-resolution Unix timestamp for machine use (the standard).
        # This float value is highly efficient for calculations and is a common standard.
        msg_timestamp = osc_message_builder.OscMessageBuilder(address="/pose/timestamp")
        msg_timestamp.add_arg(time.time())
        bundle_builder.add_content(msg_timestamp.build())
        bundleStats_totalMessages += 1

        # 0b. Add a human-readable, machine-parsable timestamp string.
        # Format: yyyy.mm.dd.hh.mm.ss.ms
        now = datetime.datetime.now()
    
        # 1. Add frame_count and num_persons to every bundle
        msg_frame_count = osc_message_builder.OscMessageBuilder(address="/pose/frame_count")
        msg_frame_count.add_arg(frame_count)
        bundle_builder.add_content(msg_frame_count.build())
        bundleStats_totalMessages += 1
        bundleStats_metaCount += 1

        msg_num_persons = osc_message_builder.OscMessageBuilder(address="/pose/num_persons")
        msg_num_persons.add_arg(len(self.latest_landmarks))
        bundle_builder.add_content(msg_num_persons.build())
        bundleStats_totalMessages += 1
        bundleStats_metaCount += 1


        # 2. Add other metadata periodically (e.g., every second)
        # Send on the first frame, and then every `fps_limit` frames thereafter.
        if fps_limit > 0 and (frame_count == 1 or frame_count % fps_limit == 0):
            ts_str = now.strftime("%Y.%m.%d.%H.%M.%S") + f".{now.microsecond // 1000:03d}"
            msg_timestamp_str = osc_message_builder.OscMessageBuilder(address="/pose/timestamp_str")
            msg_timestamp_str.add_arg(ts_str)
            bundle_builder.add_content(msg_timestamp_str.build())
            bundleStats_totalMessages += 1
            bundleStats_metaCount += 1

            msg_img_w = osc_message_builder.OscMessageBuilder(address="/pose/image_width")
            msg_img_w.add_arg(self.image_width)
            bundle_builder.add_content(msg_img_w.build())
            bundleStats_totalMessages += 1
            bundleStats_metaCount += 1

            msg_img_h = osc_message_builder.OscMessageBuilder(address="/pose/image_height")
            msg_img_h.add_arg(self.image_height)
            bundle_builder.add_content(msg_img_h.build())
            bundleStats_totalMessages += 1
            bundleStats_metaCount += 1

            # Calculate and add aspect ratio if height is valid
            if self.image_height > 0:
                aspect_ratio = float(self.image_width) / self.image_height
                msg_aspect_ratio = osc_message_builder.OscMessageBuilder(address="/pose/aspect_ratio")
                msg_aspect_ratio.add_arg(aspect_ratio)
                bundle_builder.add_content(msg_aspect_ratio.build())
                bundleStats_totalMessages += 1
                bundleStats_metaCount += 1

            # Add model name
            msg_model_name = osc_message_builder.OscMessageBuilder(address="/pose/model_name")
            msg_model_name.add_arg(self.model_name)
            bundle_builder.add_content(msg_model_name.build())
            bundleStats_totalMessages += 1
            bundleStats_metaCount += 1

            # Add the landmark name mapping.
            # This sends a list of strings, where the index corresponds to the landmark ID.
            if self.pose_id_to_name:
                # Ensure the names are sent in the correct order of their IDs
                sorted_names = [self.pose_id_to_name[i] for i in sorted(self.pose_id_to_name.keys())]
                msg_name_map = osc_message_builder.OscMessageBuilder(address="/pose/landmark_names")
                for name in sorted_names:
                    msg_name_map.add_arg(name)
                bundle_builder.add_content(msg_name_map.build())
                bundleStats_totalMessages += 1
                bundleStats_metaCount += 1

        # --- Add landmark data ---
        for person_id, skeleton in enumerate(self.latest_landmarks):
            if not skeleton:
                continue
            bundleStats_personCount +=1
            
            # Add bounding box data if available for this person
            if person_id < len(self.latest_bboxes):
                x, y, w, h = self.latest_bboxes[person_id]
                msg_bbox = osc_message_builder.OscMessageBuilder(address=f"/pose/p{person_id + 1}/bbox")
                msg_bbox.add_arg(float(x))
                msg_bbox.add_arg(float(y))
                msg_bbox.add_arg(float(w))
                msg_bbox.add_arg(float(h))
                bundle_builder.add_content(msg_bbox.build())
                bundleStats_totalMessages += 1
            
            # the impl should include xyz + visibility
            # at this time we dont send vis on thru OSC but might in future
            for landmark_id, (x, y, z, visibility) in enumerate(skeleton):
                msg = osc_message_builder.OscMessageBuilder(address=f"/pose/p{person_id + 1}/{landmark_id}")
                msg.add_arg(float(x)); msg.add_arg(float(y)); msg.add_arg(float(z))
                bundle_builder.add_content(msg.build())
                bundleStats_totalMessages += 1
                bundleStats_numLandmarks  += 1
        
        bundle = bundle_builder.build()
        
        # debug output the bundleStats each frame
        if frame_count > 0 and (frame_count % 5 == 0):
            logging.debug(f"[OSC] frame{frame_count}: Persons={bundleStats_personCount}, "
                          f"MetaMsgs={bundleStats_metaCount}, LandmarkMsgs={bundleStats_numLandmarks}, TotalMsgs={bundleStats_totalMessages}")

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