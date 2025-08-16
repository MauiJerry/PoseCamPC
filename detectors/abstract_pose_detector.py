from abc import ABC, abstractmethod
import logging
from pythonosc import udp_client, osc_bundle_builder, osc_message_builder

class AbstractPoseDetector(ABC):
    def __init__(self):
        """
        Initializes the detector.
        self.latest_landmarks is now a list of skeletons, where each skeleton is a list of landmarks.
        e.g., [ [(x1,y1,z1), (x2,y2,z2), ...], [(x1,y1,z1), ...] ]
        """
        self.latest_landmarks = []
        self._osc_bundle_log_count = 0

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