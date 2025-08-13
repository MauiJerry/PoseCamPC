#!/usr/bin/env python3
"""
Preflight sender:
- Emits a synthetic moving test pattern as an NDI video stream.
- Sends OSC metadata (/image-height, /image-width, /numLandmarks)
  and per-landmark triples at /p1/<name> [u, v, conf].
- Also sends an OSC bundle at /SYNC to test receiver bundle handling.

Tested with ndi-python (NDIlib), python-osc, opencv-python, numpy.

Usage:
  python preflight_tx.py --ndi-name PosePC-Test --osc-ip 127.0.0.1 --osc-port 5005 --fps 30 --marks 33
"""
import argparse
import math
import random
import signal
import sys
import time
from typing import List

import cv2
import numpy as np
from pythonosc import udp_client, osc_bundle_builder, osc_message_builder

try:
    import NDIlib as ndi
except ImportError:
    print("ERROR: NDIlib (ndi-python) is not installed/available. Install your local wheel, then retry.")
    sys.exit(1)

MEDIAPIPE_NAMES: List[str] = [
    'head','mp_eye_inner_l','eye_l','mp_eye_outer_l','mp_eye_inner_r','eye_r','mp_eye_outer_e',
    'mp_ear_l','mp_ear_r','mp_mouth_l','mp_mouth_r','shoulder_l','shoulder_r','elbow_l','elbow_r',
    'wrist_l','wrist_r','mp_pinky_l','mp_pinky_r','handtip_l','handtip_r','thumb_l','thumb_r',
    'hip_l','hip_r','knee_l','knee_r','ankle_l','ankle_r','mp_heel_l','mp_heel_r','foot_l','foot_r'
]

def make_test_frame(w, h, t):
    """RGBA test frame with moving box + timestamp."""
    img = np.zeros((h, w, 4), dtype=np.uint8)
    # gradient background
    yy = np.linspace(0, 255, h, dtype=np.uint8)[:, None]
    xx = np.linspace(0, 255, w, dtype=np.uint8)[None, :]
    img[..., 0] = xx  # B
    img[..., 1] = yy  # G
    img[..., 2] = ((xx.astype(int) + yy.astype(int)) % 256).astype(np.uint8)  # R
    img[..., 3] = 255  # A

    # moving square
    size = min(w, h) // 8
    cx = int((w / 2) + (w / 3) * math.sin(t * 1.5))
    cy = int((h / 2) + (h / 4) * math.cos(t * 1.2))
    x0, y0 = max(0, cx - size), max(0, cy - size)
    x1, y1 = min(w, cx + size), min(h, cy + size)
    img[y0:y1, x0:x1, :3] = (255, 255, 255)

    # timestamp text
    bgr = cv2.cvtColor(img[..., :3], cv2.COLOR_RGBA2BGR)
    cv2.putText(bgr, f"{time.strftime('%H:%M:%S')}  t={t:.2f}",
                (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2, cv2.LINE_AA)
    rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA)
    return rgba

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ndi-name", default="PosePC-Test", help="NDI stream name")
    ap.add_argument("--w", type=int, default=1280)
    ap.add_argument("--h", type=int, default=720)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--osc-ip", default="127.0.0.1")
    ap.add_argument("--osc-port", type=int, default=5005)
    ap.add_argument("--marks", type=int, default=33, choices=[17, 33], help="How many landmarks to simulate")
    args = ap.parse_args()

    # OSC setup
    osc = udp_client.SimpleUDPClient(args.osc_ip, args.osc_port)

    # NDI setup
    if not ndi.initialize():
        print("ERROR: NDI initialize() failed.")
        sys.exit(2)
    try:
        send_settings = ndi.SendCreate()
        send_settings.ndi_name = args.ndi_name
        ndi_send = ndi.send_create(send_settings)
        if ndi_send is None:
            print("ERROR: Failed to create NDI sender.")
            sys.exit(3)

        vf = ndi.VideoFrameV2()
        vf.FourCC = ndi.FOURCC_VIDEO_TYPE_RGBX  # RGBA as RGBX per NDIlib
        vf.xres, vf.yres = args.w, args.h
        vf.frame_rate_N, vf.frame_rate_D = args.fps, 1

        # generate deterministic fake landmarks in UV with jitter
        num = args.marks
        rng = random.Random(42)
        base = [(rng.random(), rng.random(), rng.uniform(-0.5, 0.5)) for _ in range(num)]

        names = MEDIAPIPE_NAMES if num == 33 else [f"lm_{i}" for i in range(num)]

        print(f"Sending NDI '{args.ndi_name}' at {args.w}x{args.h}@{args.fps} and OSC to {args.osc_ip}:{args.osc_port}")
        print("Press Ctrl+C to stop.")

        start = time.perf_counter()
        frame_idx = 0
        period = 1.0 / max(1, args.fps)

        def sigint(_sig, _frm):  # graceful exit
            raise KeyboardInterrupt()
        signal.signal(signal.SIGINT, sigint)

        while True:
            now = time.perf_counter()
            t = now - start

            # --- NDI video ---
            rgba = make_test_frame(args.w, args.h, t)
            vf.data = rgba  # numpy array
            ndi.send_send_video_v2(ndi_send, vf)

            # --- OSC meta + landmarks ---
            osc.send_message("/image-width", args.w)
            osc.send_message("/image-height", args.h)
            osc.send_message("/numLandmarks", num)

            # send triplets at /p1/<name>
            jitter_scale = 0.003
            for i, nm in enumerate(names):
                u, v, c = base[i]
                # subtle wandering to prove live updates
                u2 = (u + 0.5 + 0.1 * math.sin(0.8 * t + i)) % 1.0
                v2 = (v + 0.5 + 0.1 * math.cos(0.6 * t + i)) % 1.0
                c2 = max(-1.0, min(1.0, c + jitter_scale * math.sin(1.1 * t + i)))
                osc.send_message(f"/p1/{nm}", [float(u2), float(v2), float(c2)])
                # optional per-axis format (commented):
                # osc.send_message(f"/landmark-{i}-x", float(u2))
                # osc.send_message(f"/landmark-{i}-y", float(v2))
                # osc.send_message(f"/landmark-{i}-z", float(c2))

            # Send a small test bundle on /SYNC (build-send)
            bb = osc_bundle_builder.OscBundleBuilder(osc_bundle_builder.IMMEDIATELY)
            m = osc_message_builder.OscMessageBuilder(address="/SYNC")
            m.add_arg(frame_idx)
            m.add_arg(time.time())
            bb.add_content(m.build())
            osc.send(bb.build())
            
            frame_idx += 1
            # --- pacing ---
            dt = time.perf_counter() - now
            to_sleep = period - dt
            if to_sleep > 0:
                time.sleep(to_sleep)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        try:
            ndi.send_destroy(ndi_send)
        except Exception:
            pass
        ndi.destroy()

if __name__ == "__main__":
    main()
