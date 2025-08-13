#!/usr/bin/env python3
"""
Preflight receiver:
- Runs an OSC server and prints/validates expected messages.
- Connects to an NDI source and prints resolution/fps while frames arrive.

Usage:
  python preflight_rx.py --osc-port 5005 --ndi-source PosePC-Test

Tips:
- If multiple NDI sources exist, provide a substring of the name with --ndi-source.
- Leave --ndi-source empty to list sources and exit.
"""
import argparse
import queue
import signal
import sys
import threading
import time

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

try:
    import NDIlib as ndi
except ImportError:
    print("ERROR: NDIlib (ndi-python) is not installed/available.")
    sys.exit(1)

def osc_server_thread(port, outq: queue.Queue):
    disp = Dispatcher()

    # Basic validators/collectors
    def on_meta(addr, *args):
        outq.put(("OSC", addr, args))
    def on_lm(addr, *args):
        outq.put(("OSC", addr, args))
    def on_default(addr, *args):
        outq.put(("OSC", addr, args))

    # expected paths
    disp.map("/image-width", on_meta)
    disp.map("/image-height", on_meta)
    disp.map("/numLandmarks", on_meta)
    disp.map("/p1/*", on_lm)         # any landmark triple
    disp.map("/SYNC", on_meta)
    disp.set_default_handler(on_default)

    server = ThreadingOSCUDPServer(("0.0.0.0", port), disp)
    print(f"OSC server listening on 0.0.0.0:{port}")
    try:
        server.serve_forever()
    finally:
        server.server_close()

def find_source_by_name(substr: str):
    """Returns first NDI source whose name contains substr (case-insensitive)."""
    f = ndi.find_create_v2()
    if f is None:
        print("ERROR: find_create_v2 failed")
        return None, []
    try:
        ndi.find_wait_for_sources(f, 3000)  # wait up to 3s
        sources = ndi.find_get_current_sources(f)
    finally:
        ndi.find_destroy(f)
    if substr:
        s = next((s for s in sources if substr.lower() in s.ndi_name.lower()), None)
        return s, sources
    return None, sources

def ndi_receiver_thread(source_name_substr: str, outq: queue.Queue, stop_event: threading.Event):
    if not ndi.initialize():
        print("ERROR: NDI initialize() failed.")
        return
    try:
        src, all_sources = find_source_by_name(source_name_substr)
        if not src:
            if source_name_substr:
                print(f"NDI: No source matching '{source_name_substr}'. Available:")
            else:
                print("NDI: Provide --ndi-source. Available:")
            for i, s in enumerate(all_sources):
                print(f"  [{i}] {s.ndi_name}")
            return

        print(f"NDI: Connecting to '{src.ndi_name}'")
        rc = ndi.RecvCreateV3()
        rc.color_format = ndi.RECV_COLOR_FORMAT_BGRX
        rc.bandwidth = ndi.RECV_BANDWIDTH_HIGHEST
        rc.allow_video_fields = False
        recv = ndi.recv_create_v3(rc)
        if recv is None:
            print("ERROR: recv_create_v3 failed")
            return
        ndi.recv_connect(recv, src)

        # fps estimator
        last_ts = None
        frame_count = 0
        while not stop_event.is_set():
            t, v, a, m = ndi.recv_capture_v2(recv, 2000)  # 2s timeout
            if t == ndi.FRAME_TYPE_VIDEO:
                frame_count += 1
                now = time.perf_counter()
                if last_ts is None:
                    last_ts = now
                if frame_count % 30 == 0:
                    fps = 30.0 / (now - last_ts) if now > last_ts else 0.0
                    last_ts = now
                    outq.put(("NDI", f"{v.xres}x{v.yres}", f"{fps:.1f} fps"))
                # Always free frames you capture
                ndi.recv_free_video_v2(recv, v)
            elif t == ndi.FRAME_TYPE_NONE:
                outq.put(("NDI", "timeout/no video", "waiting..."))
        ndi.recv_destroy(recv)
    finally:
        ndi.destroy()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--osc-port", type=int, default=5005)
    ap.add_argument("--ndi-source", default="PosePC-Test", help="Substring of the NDI sender name to connect to")
    args = ap.parse_args()

    outq: queue.Queue = queue.Queue()
    stop = threading.Event()

    # Start OSC server
    osc_thr = threading.Thread(target=osc_server_thread, args=(args.osc_port, outq), daemon=True)
    osc_thr.start()

    # Start NDI receiver
    ndi_thr = threading.Thread(target=ndi_receiver_thread, args=(args.ndi_source, outq, stop), daemon=True)
    ndi_thr.start()

    def sigint(_s, _f):
        stop.set()
        print("\nStopping…")
        time.sleep(0.3)
        sys.exit(0)
    signal.signal(signal.SIGINT, sigint)

    # Simple log loop with summary counters
    seen_meta = set()
    last_print = time.time()
    osc_count = 0
    while True:
        try:
            kind, a, b = outq.get(timeout=1.0)
            if kind == "OSC":
                osc_count += 1
                if a in ("/image-width", "/image-height", "/numLandmarks"):
                    seen_meta.add(a)
                if time.time() - last_print > 0.5:
                    print(f"OSC {a} {b}")
                    last_print = time.time()
            elif kind == "NDI":
                print(f"NDI {a} {b}")
        except queue.Empty:
            pass

        # lightweight readiness check
        if len(seen_meta) == 3 and (time.time() - last_print) > 2:
            print("OK: Received OSC metadata (/image-width, /image-height, /numLandmarks). Waiting for more…")
            last_print = time.time()

if __name__ == "__main__":
    main()
