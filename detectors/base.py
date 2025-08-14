from abc import ABC, abstractmethod
from pythonosc import udp_client, osc_bundle_builder, osc_message_builder

class AbstractPoseDetector(ABC):
    def __init__(self):
        """
        Initializes the detector. self.latest_landmarks will hold a flat list
        of (x, y, z) tuples for a single detected person.
        """
        self.latest_landmarks = []

    @abstractmethod
    def process_image(self, image):
        pass

    @abstractmethod
    def draw_landmarks(self, frame):
        pass

    def send_landmarks_via_osc(self, client: udp_client.SimpleUDPClient):
        """Sends detected landmarks for a single person via OSC."""
        if not client or not self.latest_landmarks:
            return

        try:
            for idx, (x, y, z) in enumerate(self.latest_landmarks):
                client.send_message(f"/landmark-{idx}", [float(x), float(y), float(z)])
        except Exception as e:
            print(f"[OSC] Error sending landmark data: {e}")