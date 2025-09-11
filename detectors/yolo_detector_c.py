# yolo_pose_detector.py from Chat
from __future__ import annotations
from typing import List, Tuple, Dict, Optional, Any
import numpy as np
import cv2
import logging
import os
from ultralytics import YOLO

from .abstract_pose_detector import AbstractPoseDetector

# COCO-17 mapping (id order must match model output)
COCO17_ID2NAME: Dict[int, str] = {
    0: "nose",
    1: "eye_l",
    2: "eye_r",
    3: "ear_l",
    4: "ear_r",
    5: "shoulder_l",
    6: "shoulder_r",
    7: "elbow_l",
    8: "elbow_r",
    9: "wrist_l",
    10: "wrist_r",
    11: "hip_l",
    12: "hip_r",
    13: "knee_l",
    14: "knee_r",
    15: "ankle_l",
    16: "ankle_r",
}

COCO17_EDGES = [
    (5, 7), (7, 9), (6, 8), (8, 10),
    (11, 13), (13, 15), (12, 14), (14, 16),
    (5, 6), (11, 12), (5, 11), (6, 12),
    (0, 1), (0, 2), (1, 3), (2, 4),
    (5, 0), (6, 0),
]

class PoseDetectorYOLO_C(AbstractPoseDetector):
    """
    Ultralytics YOLO Pose backend emitting:
      self.latest_landmarks = [ [ (x,y,z,vis), ... ], ... ]  # normalized x,y in [0..1]
    """

    def __init__(
        self,
        model_filename: str = "yolov8n-pose.pt",
        display_name: str | None = None,
        conf: float = 0.25,
        iou: float = 0.45,
        imgsz: int = 640,
        max_det: int = 10,
        device: Optional[str] = None  # ultralytics manages device internally; keep for future
    ):
        super().__init__()

        # Fill in required meta fields
        if display_name:
            self.model_name = display_name
        else:
            self.model_name = f"YOLO-Pose:{model_filename}"

        self.schema_name = "COCO17"
        self.pose_id_to_name = COCO17_ID2NAME.copy()

        # Construct an absolute path to the model cache directory relative to this script file
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_cache_dir = os.path.join(project_root, 'model_cache')
        model_path = os.path.join(model_cache_dir, model_filename)

        if not os.path.exists(model_path):
            # --- Add diagnostic logging ---
            dir_contents = "Directory does not exist."
            if os.path.isdir(model_cache_dir):
                dir_contents = "\n".join(os.listdir(model_cache_dir))
                if not dir_contents:
                    dir_contents = "<Directory is empty>"

            error_message = (
                f"YOLO model file not found at: {model_path}\n"
                f"\nContents of '{model_cache_dir}':\n---\n{dir_contents}\n---\n"
                f"Please download '{model_filename}' manually and place it in the '{model_cache_dir}' directory.\n"
                "You can find official models on the Ultralytics GitHub releases page."
            )
            logging.error(error_message)
            raise FileNotFoundError(error_message)

        try:
            self._model = YOLO(model_path)
        except Exception as e:
            error_message = (
                f"Failed to load YOLO model from path: {model_path}\n"
                f"Error: {e}\n"
                "The file may be corrupt. Try deleting it and downloading it again."
            )
            logging.error(error_message)
            raise RuntimeError(error_message) from e
        self._conf = conf
        self._iou = iou
        self._imgsz = imgsz
        self._max_det = max_det

        # for draw cache
        self._last_px: List[np.ndarray] = []

    def process_image(self, image_bgr) -> Any:
        if image_bgr is None or image_bgr.size == 0:
            self.latest_landmarks = []
            self.latest_bboxes = []
            self._last_px = []
            return None

        H, W = image_bgr.shape[:2]
        self.image_height, self.image_width = H, W

        results = self._model.predict(
            source=image_bgr,
            imgsz=self._imgsz,
            conf=self._conf,
            iou=self._iou,
            max_det=self._max_det,
            verbose=False,
        )
        if not results:
            self.latest_landmarks = []
            self.latest_bboxes = []
            self._last_px = []
            return None

        r = results[0]
        kps = getattr(r, "keypoints", None)
        boxes = getattr(r, "boxes", None)
        if kps is None or boxes is None:
            self.latest_landmarks = []
            self.latest_bboxes = []
            self._last_px = []
            return r

        # Extract xy and confidences
        if hasattr(kps, "xy"):
            k_xy = kps.xy.cpu().numpy()      # [N, 17, 2] in pixels
        else:
            # fallback to .data[..., :2] shape
            k_xy = kps.data[..., :2].cpu().numpy()

        if getattr(kps, "conf", None) is not None:
            k_cf = kps.conf.cpu().numpy()    # [N, 17] in [0..1]
        else:
            det_conf = boxes.conf.cpu().numpy() if hasattr(boxes, "conf") else None
            if det_conf is None:
                k_cf = np.ones((k_xy.shape[0], k_xy.shape[1]), dtype=np.float32)
            else:
                k_cf = np.tile(det_conf.reshape(-1, 1), (1, k_xy.shape[1]))

        # Extract bounding boxes
        bboxes_norm = boxes.xywhn.cpu().numpy() if hasattr(boxes, "xywhn") else None

        self._last_px = []
        out: List[List[Tuple[float, float, float, float]]] = []
        out_bboxes: List[Tuple[float, float, float, float]] = []

        for i in range(k_xy.shape[0]):  # per person
            person_xy = k_xy[i]         # [17, 2]
            person_cf = k_cf[i]         # [17]
            self._last_px.append(person_xy.astype(np.float32))

            # Add corresponding bounding box
            if bboxes_norm is not None and i < len(bboxes_norm):
                x, y, w, h = bboxes_norm[i]
                out_bboxes.append((float(x), float(y), float(w), float(h)))

            # Normalize to [0..1] to match MP-style downstream consumers
            person_norm: List[Tuple[float, float, float, float]] = []
            for j in range(person_xy.shape[0]):
                px = float(np.clip(person_xy[j, 0], 0, W - 1))
                py = float(np.clip(person_xy[j, 1], 0, H - 1))
                nx = px / float(W)
                ny = py / float(H)
                vis = float(np.clip(person_cf[j], 0.0, 1.0))
                person_norm.append((nx, ny, 0.0, vis))  # z=0 for 2D backend
            out.append(person_norm)

        self.latest_landmarks = out
        self.latest_bboxes = out_bboxes
        return r

    def draw_landmarks(self, frame, draw_bbox: bool, use_native_plot: bool) -> None:
        # This detector has no separate "native plot", its manual implementation is the only one.
        # We ignore `use_native_plot`.

        h, w, _ = frame.shape

        if draw_bbox:
            for (cx, cy, bw, bh) in self.latest_bboxes:
                x1 = int((cx - bw / 2) * w)
                y1 = int((cy - bh / 2) * h)
                x2 = int((cx + bw / 2) * w)
                y2 = int((cy + bh / 2) * h)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 1)

        if not self._last_px:
            return
        for person_xy in self._last_px:
            for (x, y) in person_xy:
                cv2.circle(frame, (int(x), int(y)), 3, (255, 255, 255), -1)
            for a, b in COCO17_EDGES:
                xa, ya = person_xy[a]
                xb, yb = person_xy[b]
                cv2.line(frame, (int(xa), int(ya)), (int(xb), int(yb)), (200, 200, 200), 1)
