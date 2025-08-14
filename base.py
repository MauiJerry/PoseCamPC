from abc import ABC, abstractmethod
from pythonosc import udp_client, osc_bundle_builder, osc_message_builder

class AbstractPoseDetector(ABC):
    def __init__(self):
        """
        Initializes the detector.
        self.latest_landmarks is now a list of skeletons, where each skeleton is a list of landmarks.
        e.g., [ [(x1,y1,z1), (x2,y2,z2), ...], [(x1,y1,z1), ...] ]
        """
        self.latest_landmarks = []

    @abstractmethod
    def process_image(self, image):
        pass

    @abstractmethod
    def draw_landmarks(self, frame):
        pass

    def send_landmarks_via_osc(self, client: udp_client.SimpleUDPClient):
        if not client or not self.latest_landmarks:
            return

        # Use a bundle to send all data for a single frame at once for efficiency
        bundle_builder = osc_bundle_builder.OscBundleBuilder(osc_bundle_builder.IMMEDIATELY)

        # Iterate through each detected person (skeleton)
        for person_id, skeleton in enumerate(self.latest_landmarks):
            if not skeleton:
                continue
            
            # Iterate through each landmark in the skeleton and create a message
            for landmark_id, (x, y, z) in enumerate(skeleton):
                msg = osc_message_builder.OscMessageBuilder(address=f"/pose/{person_id}/{landmark_id}")
                msg.add_arg(float(x)); msg.add_arg(float(y)); msg.add_arg(float(z))
                bundle_builder.add_content(msg.build())
        
        try:
            client.send(bundle_builder.build())
        except Exception as e:
            print(f"[OSC] Error sending landmark bundle: {e}")

