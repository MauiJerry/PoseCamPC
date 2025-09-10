import tkinter as tk
from tkinter import filedialog, scrolledtext
import threading
import os
import time
import logging
import datetime
from functools import partial

from core.controller import PoseCamController, AppState
from detectors import (
    PoseDetectorMediapipe,
    PoseDetectorYOLO_G,
    PoseDetectorYOLO_C,
    # PoseDetectorYOLO_Seg,
    PoseDetectorMediaPipeTask
)

# --- Model Configuration ---
# order in list deteermines order of test 
AVAILABLE_DETECTORS = {
    # "YOLOv8 Pose+Seg": PoseDetectorYOLO_Seg, # This model is very slow (~12fps)
    "MediaPipe Task API": partial(PoseDetectorMediaPipeTask, output_segmentation=False),
    "MediaPipe Task API +Seg": partial(PoseDetectorMediaPipeTask, output_segmentation=True),
    "MediaPipe Legacy": PoseDetectorMediapipe,
    "YOLOv11 (Simple)": partial(PoseDetectorYOLO_G, model_filename='yolo11n-pose.pt', display_name="YOLOv11 (Simple)"), # NOTE: Requires manual download
    "YOLOv8 (Simple)": partial(PoseDetectorYOLO_G, model_filename='yolov8n-pose.pt', display_name="YOLOv8 (Simple)"),
#   "YOLOv8 (Complex)": PoseDetectorYOLO_C,
}

class BatchTesterGUI:
    def __init__(self, root, controller):
        self.root = root
        self.controller = controller
        self.root.title("PoseCam Batch Performance Tester")
        self.root.geometry("600x400")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.folder_path = tk.StringVar()
        self.config_file = "batch_tester.cfg"

        # --- UI Widgets ---
        top_frame = tk.Frame(self.root, padx=10, pady=10)
        top_frame.pack(fill=tk.X)

        folder_label = tk.Label(top_frame, text="Video Folder:")
        folder_label.pack(side=tk.LEFT)

        folder_entry = tk.Entry(top_frame, textvariable=self.folder_path, state="readonly")
        folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self.btn_select_folder = tk.Button(top_frame, text="Select Folder...", command=self.select_folder)
        self.btn_select_folder.pack(side=tk.LEFT)

        self.btn_start_batch = tk.Button(self.root, text="Start Batch Test", command=self.start_batch_test, state=tk.DISABLED, font=("Arial", 12, "bold"))
        self.btn_start_batch.pack(pady=10, fill=tk.X, padx=10)

        self.log_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, state=tk.DISABLED, bg="black", fg="lightgray")
        self.log_area.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        self.load_last_folder()

    def log(self, message):
        """Appends a message to the log area in a thread-safe way."""
        def _append():
            self.log_area.config(state=tk.NORMAL)
            self.log_area.insert(tk.END, message + "\n")
            self.log_area.see(tk.END)
            self.log_area.config(state=tk.DISABLED)
        self.root.after(0, _append)

    def load_last_folder(self):
        """Loads the last used folder path from the config file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    last_folder = f.read().strip()
                if os.path.isdir(last_folder):
                    self.folder_path.set(last_folder)
                    self.btn_start_batch.config(state=tk.NORMAL)
                    self.log(f"Loaded last used folder: {last_folder}")
                else:
                    self.log("Last used folder not found. Please select a new one.")
        except Exception as e:
            self.log(f"Could not load config file: {e}")

    def save_last_folder(self, folder):
        """Saves the given folder path to the config file."""
        try:
            with open(self.config_file, 'w') as f:
                f.write(folder)
        except Exception as e:
            self.log(f"Could not save config file: {e}")

    def select_folder(self):
        # Determine initial directory for the dialog
        initial_dir = self.folder_path.get()
        if not initial_dir or not os.path.isdir(initial_dir):
            initial_dir = "videoSamples"
            if not os.path.isdir(initial_dir):
                initial_dir = os.getcwd()

        folder_selected = filedialog.askdirectory(title="Select Folder with Video Files", initialdir=initial_dir)
        if folder_selected:
            self.folder_path.set(folder_selected)
            self.btn_start_batch.config(state=tk.NORMAL)
            self.log(f"Selected folder: {folder_selected}")
            self.save_last_folder(folder_selected)

    def start_batch_test(self):
        self.btn_start_batch.config(state=tk.DISABLED)
        self.btn_select_folder.config(state=tk.DISABLED)
        
        # Run the batch process in a separate thread to not freeze the GUI
        batch_thread = threading.Thread(target=self.run_batch_process, daemon=True)
        batch_thread.start()

    def run_batch_process(self):
        folder = self.folder_path.get()
        if not folder:
            self.log("ERROR: No folder selected.")
            return

        video_files = []
        try:
            video_extensions = ('.mp4', '.mov', '.avi', '.mkv')
            for filename in sorted(os.listdir(folder)):
                if filename.lower().endswith(video_extensions):
                    video_files.append(os.path.join(folder, filename))
        except Exception as e:
            self.log(f"ERROR: Could not read video files from folder: {e}")
            return
        
        if not video_files:
            self.log("No video files found in the selected folder.")
            self.root.after(0, lambda: self.btn_select_folder.config(state=tk.NORMAL))
            return

        self.log(f"Found {len(video_files)} video(s) to test.")
        
        # Start output streams with default settings
        self.log("Starting NDI and OSC outputs...")
        self.controller.start_ndi()
        self.controller.start_osc()

        # --- Configuration for the test run ---
        # Set this to True to also test performance without the overlay drawn.
        # By default, only the performance with the overlay is tested.
        TEST_WITHOUT_OVERLAY = False

        detector_names = list(self.controller.available_detectors.keys())
        overlay_options = [True, False] if TEST_WITHOUT_OVERLAY else [True]
        total_runs = len(video_files) * len(detector_names) * len(overlay_options)
        current_run = 0

        try:
            # --- Main Test Loop ---
            for model_name in detector_names:
                for video_file in video_files:
                    for overlay_enabled in overlay_options:
                        current_run += 1
                        self.log("-" * 50)
                        self.log(f"Run {current_run}/{total_runs}:")
                        self.log(f"  Model: {model_name}")
                        self.log(f"  File: {os.path.basename(video_file)}")
                        self.log(f"  Overlay: {'On' if overlay_enabled else 'Off'}")

                        # Configure the controller for this run (must be done while stopped)
                        self.controller.change_detector_model(model_name)
                        self.controller.update_config('video_file', video_file)
                        self.controller.update_config('input', 'file')
                        self.controller.update_config('loop_video', False) # Ensure video ends
                        self.controller.update_config('draw_ndi_overlay', overlay_enabled)
                        
                        self.controller.start() # Start processing

                        # Wait for the controller to finish the file
                        while self.controller.state in [AppState.RUNNING, AppState.PAUSED]:
                            time.sleep(0.5)
                        
                        self.log("  ... Run complete.")
                        time.sleep(1) # Small delay between runs
        except Exception as e:
            self.log("=" * 50)
            self.log("FATAL ERROR: Batch test halted.")
            self.log(f"Details: {e}")
            logging.exception("A critical error occurred during the batch test:")
            self.log("Please check the log file for the full traceback.")
            return # Stop the batch process

        self.log("=" * 50)
        self.log("BATCH TESTING COMPLETE!")
        self.log(f"Performance data saved to: {self.controller.perf_log_file}")
        self.log("You can now close this window.")
        self.root.after(5000, self.on_closing) # Auto-close after 5 seconds

    def on_closing(self):
        self.log("Shutting down...")
        self.controller.shutdown()
        self.root.destroy()

if __name__ == "__main__":
    # --- Setup comprehensive logging ---
    log_timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f"batch_test_run_{log_timestamp}.log"
    
    # Configure logging to write to both a file and the console
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        handlers=[logging.FileHandler(log_filename), logging.StreamHandler()]
    )

    controller = PoseCamController(AVAILABLE_DETECTORS)
    processing_thread = threading.Thread(target=controller.run, daemon=True)
    processing_thread.start()
    root = tk.Tk()
    gui = BatchTesterGUI(root, controller)
    root.mainloop()