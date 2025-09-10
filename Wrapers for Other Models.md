### Drop-in detectors for MoveNet, OpenPifPaf, MMPose, and “OpenPose (OpenCV-DNN)”

Below are **four detectors** that match your `AbstractPoseDetector` interface and your existing YOLO/MediaPipe styles. Each includes install + model setup notes and focuses on returning:

- `self.latest_landmarks = [ [ (x,y,z,vis), … ], … ]` (normalized **[0..1]** x,y; z=0.0 if 2D)
- `self.pose_id_to_name` populated for the skeleton being used
- `self.model_name` for your OSC metadata

(They follow the same contracts you’re already using in `AbstractPoseDetector` and the YOLO / MediaPipe examples.)   

------

### MoveNet (TF-Lite Thunder/Lightning)

**Install**

```bash
pip install numpy opencv-python tensorflow==2.16.1  # or your TF of choice
# Optional: smaller runtime instead of full TF if CPU-only:
# pip install tflite-runtime
```

**Model files (put in `model_cache/`):**

- Download TF-Lite: `movenet_thunder.tflite` or `movenet_lightning.tflite` (single-person).
  - Place at: `project_root/model_cache/movenet_thunder.tflite`

**Detector: `detectors/movenet_detector.py`**

```python
# movenet_detector.py
from __future__ import annotations
import os, cv2, numpy as np
from typing import List, Tuple
try:
    import tflite_runtime.interpreter as tflite  # if installed
except Exception:
    import tensorflow.lite as tflite  # fallback via full TF
from .abstract_pose_detector import AbstractPoseDetector

# COCO-17 style ids to stay consistent with your YOLO-17 mapping
COCO17_ID2NAME = {
    0:"nose", 1:"eye_l", 2:"eye_r", 3:"ear_l", 4:"ear_r",
    5:"shoulder_l", 6:"shoulder_r", 7:"elbow_l", 8:"elbow_r",
    9:"wrist_l", 10:"wrist_r", 11:"hip_l", 12:"hip_r",
    13:"knee_l", 14:"knee_r", 15:"ankle_l", 16:"ankle_r",
}

class PoseDetectorMoveNet(AbstractPoseDetector):
    def __init__(self, model_filename: str = "movenet_thunder.tflite"):
        super().__init__()
        self.model_name = f"MoveNet({model_filename})"
        self.pose_id_to_name = COCO17_ID2NAME.copy()

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_path = os.path.join(project_root, "model_cache", model_filename)
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"MoveNet model not found: {model_path}")

        self.interp = tflite.Interpreter(model_path=model_path)
        self.interp.allocate_tensors()
        self.input_details = self.interp.get_input_details()
        self.output_details = self.interp.get_output_details()

        # MoveNet thunder is 256x256, lightning is 192x192
        self.in_h = self.input_details[0]["shape"][1]
        self.in_w = self.input_details[0]["shape"][2]

    def _preprocess(self, bgr):
        img = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (self.in_w, self.in_h), interpolation=cv2.INTER_LINEAR)
        img = np.expand_dims(img.astype(np.uint8), axis=0)  # uint8 model
        return img

    def process_image(self, image_bgr):
        if image_bgr is None or image_bgr.size == 0:
            self.latest_landmarks = []
            return None
        H, W = image_bgr.shape[:2]
        self.image_height, self.image_width = H, W

        inp = self._preprocess(image_bgr)
        self.interp.set_tensor(self.input_details[0]['index'], inp)
        self.interp.invoke()

        # Output: [1,1,17,3] -> y,x,score
        out = self.interp.get_tensor(self.output_details[0]['index'])
        keypoints = out[0,0]  # [17,3]

        skeleton = []
        for kid in range(17):
            y, x, conf = keypoints[kid]
            nx, ny = float(x), float(y)                 # already [0..1]
            skeleton.append((nx, ny, 0.0, float(conf))) # z=0.0
        self.latest_landmarks = [skeleton]
        return out

    def draw_landmarks(self, frame):
        if not self.latest_landmarks:
            return
        H, W = frame.shape[:2]
        for (nx, ny, _, v) in self.latest_landmarks[0]:
            if v > 0.1:
                cv2.circle(frame, (int(nx*W), int(ny*H)), 3, (0,255,0), -1)
```

------

### OpenPifPaf (bottom-up multi-person)

**Install**

```bash
pip install openpifpaf opencv-python
```

(OpenPifPaf will download its weights on first use and cache them in your user dir. You can also pre-download and point `OPENPIFPAF_HOME` to your `model_cache` if you want a project-local cache.)

**Detector: `detectors/openpifpaf_detector.py`**

```python
# openpifpaf_detector.py
from __future__ import annotations
import cv2, numpy as np
from typing import List, Tuple
import openpifpaf
from .abstract_pose_detector import AbstractPoseDetector

# COCO-17 map to keep downstream consistent
COCO17_ID2NAME = {
    0:"nose", 1:"eye_l", 2:"eye_r", 3:"ear_l", 4:"ear_r",
    5:"shoulder_l", 6:"shoulder_r", 7:"elbow_l", 8:"elbow_r",
    9:"wrist_l", 10:"wrist_r", 11:"hip_l", 12:"hip_r",
    13:"knee_l", 14:"knee_r", 15:"ankle_l", 16:"ankle_r",
}

class PoseDetectorOpenPifPaf(AbstractPoseDetector):
    def __init__(self, checkpoint: str = "resnet50"):
        super().__init__()
        self.model_name = f"OpenPifPaf({checkpoint})"
        self.pose_id_to_name = COCO17_ID2NAME.copy()
        self.predictor = openpifpaf.Predictor(checkpoint=checkpoint)

    def process_image(self, image_bgr):
        if image_bgr is None or image_bgr.size == 0:
            self.latest_landmarks = []
            return None
        H, W = image_bgr.shape[:2]
        self.image_height, self.image_width = H, W

        # PifPaf expects RGB
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        preds, _, _ = self.predictor.numpy_image(rgb)
        # preds is a list of annotations; each has .data (Nx3 x,y,conf) for 17 joints
        out = []
        for ann in preds:
            if ann.data is None or ann.data.shape[0] < 17:
                continue
            person = ann.data[:17]  # [17,3]
            skel = []
            for j in range(17):
                x, y, c = person[j]
                nx = float(np.clip(x, 0, W-1))/W
                ny = float(np.clip(y, 0, H-1))/H
                skel.append((nx, ny, 0.0, float(c)))
            out.append(skel)
        self.latest_landmarks = out
        return preds

    def draw_landmarks(self, frame):
        if not self.latest_landmarks:
            return
        H, W = frame.shape[:2]
        for skel in self.latest_landmarks:
            for (nx, ny, _, v) in skel:
                if v > 0.1:
                    cv2.circle(frame, (int(nx*W), int(ny*H)), 3, (0,255,0), -1)
```

------

### MMPose (RTMPose via high-level Inferencer)

**Install (CPU quick-start)**

```bash
pip install "mmpose>=1.3.0" "mmengine>=0.10.0" "mmcv>=2.0.0"
# If you already have PyTorch+CUDA, ensure versions are compatible with your torch.
```

> MMPose downloads configs/weights on first run into a cache (usually `~/.cache/mim` or `~/.cache/mmpose`). You can also pre-stage files under your project’s `model_cache/` and pass explicit `model`/`detector` arguments if you prefer.

**Detector: `detectors/mmpose_detector.py`**

```python
# mmpose_detector.py
from __future__ import annotations
import cv2, numpy as np
from typing import List, Tuple
from mmpose.apis import MMPoseInferencer
from .abstract_pose_detector import AbstractPoseDetector

# We'll use a common 17-kp COCO head (RTMPose-s) for parity with YOLO/MoveNet.
COCO17_ID2NAME = {
    0:"nose", 1:"eye_l", 2:"eye_r", 3:"ear_l", 4:"ear_r",
    5:"shoulder_l", 6:"shoulder_r", 7:"elbow_l", 8:"elbow_r",
    9:"wrist_l", 10:"wrist_r", 11:"hip_l", 12:"hip_r",
    13:"knee_l", 14:"knee_r", 15:"ankle_l", 16:"ankle_r",
}

class PoseDetectorMMPose(AbstractPoseDetector):
    def __init__(self,
                 pose_model: str = "rtmpose-s",         # pose model alias
                 det_model: str = "rtmdet_tiny_320-8xb32_coco",  # detector alias
                 device: str = "cpu"):
        super().__init__()
        self.model_name = f"MMPose({pose_model}+{det_model})"
        self.pose_id_to_name = COCO17_ID2NAME.copy()
        # High-level pipeline: detector + top-down pose
        self.infer = MMPoseInferencer(pose_model=pose_model, det_model=det_model, device=device)

        # internal buffer to hold last results
        self._last = None

    def process_image(self, image_bgr):
        if image_bgr is None or image_bgr.size == 0:
            self.latest_landmarks = []
            return None
        H, W = image_bgr.shape[:2]
        self.image_height, self.image_width = H, W

        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        result_gen = self.infer(rgb, return_vis=False, show=False)
        result = next(result_gen)  # single image -> one result
        self._last = result

        # result['predictions'] -> list of persons -> each has 'keypoints' (Nx3 x,y,score) with N=17
        self.latest_landmarks = []
        preds = result.get('predictions', [])
        for p in preds:
            kps = p.get('keypoints', None)
            if kps is None or kps.shape[0] < 17:
                continue
            skel = []
            for j in range(17):
                x, y, s = kps[j]
                nx = float(np.clip(x, 0, W-1))/W
                ny = float(np.clip(y, 0, H-1))/H
                skel.append((nx, ny, 0.0, float(s)))
            self.latest_landmarks.append(skel)
        return result

    def draw_landmarks(self, frame):
        if not self.latest_landmarks:
            return
        H, W = frame.shape[:2]
        for skel in self.latest_landmarks:
            for (nx, ny, _, v) in skel:
                if v > 0.1:
                    cv2.circle(frame, (int(nx*W), int(ny*H)), 3, (0,255,0), -1)
```

------

### “OpenPose” via OpenCV-DNN (Caffe body_25/coco_18)

OpenPose’s official Python binding (pyopenpose) is heavy to build. A simpler, portable route is **OpenCV DNN** with the original Caffe models.

**Install**

```bash
pip install opencv-python
```

**Model files (put in `model_cache/`):**

- **COCO-18**: `pose_deploy_linevec.prototxt`, `pose_iter_440000.caffemodel`
  - Place at `model_cache/openpose/coco/…`

**Detector: `detectors/openpose_opencv_detector.py`**

```python
# openpose_opencv_detector.py
from __future__ import annotations
import os, cv2, numpy as np
from typing import List, Tuple
from .abstract_pose_detector import AbstractPoseDetector

# COCO-18 -> collapse to 17 by dropping "neck" or remapping; we’ll emit 17 COCO joints for parity.
# OpenCV’s output order is the OpenPose COCO set (0..17, where 1 is neck). We’ll drop neck (1).
OPENPOSE_COCO18_TO_COCO17 = {
    0:0,   # nose -> nose
    1:None,# neck -> drop
    2:5, 3:7, 4:9,   # R-shoulder, R-elbow, R-wrist  (OpenPose Right=our Right)
    5:6, 6:8, 7:10,  # L-shoulder, L-elbow, L-wrist
    8:11, 9:13, 10:15, # R-hip, R-knee, R-ankle
    11:12, 12:14, 13:16, # L-hip, L-knee, L-ankle
    14:1, 15:3, 16:2, 17:4  # REye, LEye, REar, LEar -> map to our indices
}

COCO17_ID2NAME = {
    0:"nose", 1:"eye_l", 2:"eye_r", 3:"ear_l", 4:"ear_r",
    5:"shoulder_l", 6:"shoulder_r", 7:"elbow_l", 8:"elbow_r",
    9:"wrist_l", 10:"wrist_r", 11:"hip_l", 12:"hip_r",
    13:"knee_l", 14:"knee_r", 15:"ankle_l", 16:"ankle_r",
}

class PoseDetectorOpenPoseOpenCV(AbstractPoseDetector):
    def __init__(self,
                 prototxt: str = "openpose/coco/pose_deploy_linevec.prototxt",
                 caffemodel: str = "openpose/coco/pose_iter_440000.caffemodel",
                 input_size=(368, 368),
                 conf_thresh: float = 0.05):
        super().__init__()
        self.model_name = "OpenPose(OpenCV-DNN COCO-18→17)"
        self.pose_id_to_name = COCO17_ID2NAME.copy()

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        mc = os.path.join(project_root, "model_cache")
        proto_path = os.path.join(mc, prototxt)
        caffe_path = os.path.join(mc, caffemodel)
        if not (os.path.exists(proto_path) and os.path.exists(caffe_path)):
            raise FileNotFoundError(f"Missing OpenPose Caffe files:\n{proto_path}\n{caffe_path}")

        self.net = cv2.dnn.readNetFromCaffe(proto_path, caffe_path)
        self.in_w, self.in_h = input_size
        self.conf_thresh = conf_thresh

    def process_image(self, image_bgr):
        if image_bgr is None or image_bgr.size == 0:
            self.latest_landmarks = []
            return None
        H, W = image_bgr.shape[:2]
        self.image_height, self.image_width = H, W

        blob = cv2.dnn.blobFromImage(image_bgr, 1.0/255, (self.in_w, self.in_h),
                                     (0,0,0), swapRB=False, crop=False)
        self.net.setInput(blob)
        out = self.net.forward()  # shape: [1, 57, Hout, Wout] -> 18 heatmaps + PAFs; we care 18 heatmaps
        heatmaps = out[0, :18, :, :]  # [18, Hout, Wout]

        # Simple argmax per joint (single person)
        Hh, Wh = heatmaps.shape[1:]
        coords = []
        for jid in range(18):
            hm = heatmaps[jid]
            _, conf, _, point = cv2.minMaxLoc(hm)
            x, y = point
            nx = x / (Wh - 1)
            ny = y / (Hh - 1)
            coords.append((nx, ny, float(conf)))

        # Remap to COCO-17 (drop neck)
        skel17 = [None]*17
        for op_id, triple in enumerate(coords):
            nx, ny, conf = triple
            tgt = OPENPOSE_COCO18_TO_COCO17.get(op_id, None)
            if tgt is None: 
                continue
            skel17[tgt] = (nx, ny, 0.0, conf)

        # Fill missing with low vis
        for i in range(17):
            if skel17[i] is None:
                skel17[i] = (0.0, 0.0, 0.0, 0.0)

        self.latest_landmarks = [skel17]
        return out

    def draw_landmarks(self, frame):
        if not self.latest_landmarks:
            return
        H, W = frame.shape[:2]
        for (nx, ny, _, v) in self.latest_landmarks[0]:
            if v > 0.1:
                cv2.circle(frame, (int(nx*W), int(ny*H)), 3, (0,255,0), -1)
```

------

### Where to put files

- Save each code block under `detectors/` in your repo:
  - `movenet_detector.py`
  - `openpifpaf_detector.py`
  - `mmpose_detector.py`
  - `openpose_opencv_detector.py`
- Ensure your **`model_cache/`** exists at project root (your YOLO / MediaPipe TaskAPI already follow this pattern).  

------

### Quick “factory” wiring (optional)

Hook these into your detector factory (where you pick a backend from CLI/UI):

```python
# detectors/__init__.py (example)
from .movenet_detector import PoseDetectorMoveNet
from .openpifpaf_detector import PoseDetectorOpenPifPaf
from .mmpose_detector import PoseDetectorMMPose
from .openpose_opencv_detector import PoseDetectorOpenPoseOpenCV

def create_detector(kind: str, **kw):
    kind = (kind or "").lower()
    if kind == "movenet":
        return PoseDetectorMoveNet(**kw)
    if kind == "openpifpaf":
        return PoseDetectorOpenPifPaf(**kw)
    if kind == "mmpose":
        return PoseDetectorMMPose(**kw)
    if kind in ("openpose", "openpose-ocv"):
        return PoseDetectorOpenPoseOpenCV(**kw)
    raise ValueError(f"Unknown detector kind: {kind}")
```

------

### Notes & gotchas

- **Performance**: MoveNet (Lightning) is the speed champ on CPU; Thunder is more accurate. OpenPifPaf is bottom-up (multi-person) and heavier. MMPose performance depends on your chosen `pose_model`/`det_model`.
- **Caching**: OpenPifPaf/MMPose auto-cache weights outside your repo by default. If you want to keep **everything inside `model_cache/`**, set their respective env vars (e.g., `OPENPIFPAF_HOME`) or pass explicit paths to configs/ckpts.
- **Keypoint schema**: All four wrappers emit **COCO-17** ids/names to make your new TD mapper trivial (same mapping you already used for YOLO-17). Your MediaPipe-33 path remains as-is and is selected at runtime by your meta → table swapper.

------