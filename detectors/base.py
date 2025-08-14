import cv2
import NDIlib as ndi
import numpy as np

class AbstractPoseDetector:
    def __init__(self):
        self.latest_landmarks = []

    def process_image(self, image):
        raise NotImplementedError("process_image must be implemented by subclass")

    def send_landmarks_via_osc(self, osc_client):
        if not osc_client or not self.latest_landmarks:
            return
        for idx, (x, y, z) in enumerate(self.latest_landmarks):
            osc_client.send_message(f"/landmark-{idx}", [x, y, z])

    def send_video_via_ndi(self, image, ndi_sender):
        if ndi_sender is None or image is None:
            return
        frame_rgba = cv2.cvtColor(image, cv2.COLOR_BGR2RGBA)
        height, width, _ = frame_rgba.shape
        video_frame = ndi.VideoFrameV2()
        video_frame.data = frame_rgba
        video_frame.FourCC = ndi.FOURCC_VIDEO_TYPE_RGBX
        video_frame.line_stride_in_bytes = frame_rgba.strides[0]
        video_frame.xres = width
        video_frame.yres = height
        ndi.send_send_video_v2(ndi_sender, video_frame)

    def draw_landmarks(self, frame):
        pass  # Optional