import tkinter as tk
from tkinter import filedialog
import queue
import cv2
from PIL import Image, ImageTk


g_webcam ="Webcam"

class PoseCamGUI:
    def __init__(self, controller):
        self.controller = controller
        self.root = tk.Tk()
        self.root.title("PoseCam Controller")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # --- Tkinter Variables ---
        # These act as a link between the UI widgets and the data.
        # They are initialized with values from the controller's config.
        self.selected_camera = tk.StringVar(value=g_webcam)
        self.camera_map = {} # To map names back to IDs

        self.ndi_name = tk.StringVar(value=self.controller.config['ndi_name'])
        self.osc_ip = tk.StringVar(value=self.controller.config['osc_ip'])
        self.osc_port = tk.StringVar(value=str(self.controller.config['osc_port']))
        self.loop_video = tk.BooleanVar(value=self.controller.config['loop_video'])
        self.draw_ndi_overlay = tk.BooleanVar(value=self.controller.config['draw_ndi_overlay'])
        self.video_file_path = tk.StringVar(value=self.controller.config.get('video_file') or "")
        self.input_source = tk.StringVar(value=self.controller.config['input'])
        self.video_info_text = tk.StringVar(value="")
        self.selected_detector = tk.StringVar()

        # Add traces to automatically update the controller when the user types
        self.ndi_name.trace_add("write", self._on_ndi_name_change)
        self.osc_ip.trace_add("write", self._on_osc_ip_change)
        self.osc_port.trace_add("write", self._on_osc_port_change)

        # To hold the PhotoImage and prevent garbage collection
        self.preview_image = None
        self.preview_canvas_image_id = None
        self.preview_canvas_text_id = None

        self.create_widgets()
        # Set initial state of input widgets based on the loaded config
        self._update_input_widget_states()

    def create_widgets(self):
        controls_frame = tk.Frame(self.root)
        controls_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        # --- Main control buttons ---
        self.btn_start_all = tk.Button(controls_frame, text="Start All", command=self.start_all, font=("Arial", 10, "bold"), bg="#d0f0c0")
        self.btn_stop_all = tk.Button(controls_frame, text="Stop All", command=self.stop_all, font=("Arial", 10, "bold"), bg="#f0c0c0", state=tk.DISABLED)
        self.btn_start = tk.Button(controls_frame, text="Start Video", command=self.start_video)
        self.btn_stop = tk.Button(controls_frame, text="Stop Video", command=self.stop_video, state=tk.DISABLED)
        self.btn_pause = tk.Button(controls_frame, text="Pause Video", command=self.pause_video, state=tk.DISABLED)
        self.btn_start_all.pack(pady=(5, 2), fill=tk.X)
        self.btn_stop_all.pack(pady=(2, 10), fill=tk.X)
        self.btn_start.pack(pady=5, fill=tk.X)
        self.btn_stop.pack(pady=5, fill=tk.X)
        self.btn_pause.pack(pady=5, fill=tk.X)

        # --- Video Preview Canvas ---
        preview_frame = tk.LabelFrame(self.root, text="Preview", padx=5, pady=5)
        preview_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.preview_canvas = tk.Canvas(preview_frame, bg="black", width=640, height=480)
        self.preview_canvas.pack(fill=tk.BOTH, expand=True)
        self.preview_canvas_text_id = self.preview_canvas.create_text(
            320, 240, anchor=tk.CENTER, text="Waiting for video stream...\nPress 'Start Video' to begin.",
            fill="white", font=("Arial", 12)
        )

        # --- Input selection frame ---
        input_frame = tk.LabelFrame(controls_frame, text="Input Source", padx=10, pady=10)
        input_frame.pack(pady=10, fill=tk.X)

        # Radio buttons for source selection
        webcam_radio = tk.Radiobutton(input_frame, text="Webcam", variable=self.input_source, value='webcam', command=self._on_source_change)
        file_radio = tk.Radiobutton(input_frame, text="File", variable=self.input_source, value='file', command=self._on_source_change)
        webcam_radio.grid(row=0, column=0, sticky='w', pady=(0, 5))
        file_radio.grid(row=1, column=0, sticky='w', pady=(0, 5))

        # Camera selection dropdown
        cam_label = tk.Label(input_frame, text="Device:")
        self.cam_dropdown = tk.OptionMenu(input_frame, self.selected_camera, "No cameras found")
        self.cam_dropdown.config(state="disabled") # Initially disabled

        cam_label.grid(row=0, column=1, sticky="e", padx=(10, 2))
        self.cam_dropdown.grid(row=0, column=2, sticky="ew")

        # Video file selection button
        self.btn_file = tk.Button(input_frame, text="Select...", command=self.select_file)
        self.file_entry = tk.Entry(input_frame, textvariable=self.video_file_path, state="readonly")

        self.btn_file.grid(row=1, column=1, sticky="ew", padx=(10, 0))
        self.file_entry.grid(row=1, column=2, sticky="ew")

        # Video looping checkbox
        self.loop_check = tk.Checkbutton(input_frame, text="Loop Video", variable=self.loop_video, command=self._on_loop_change)
        self.loop_check.grid(row=2, column=2, sticky='w', pady=5)

        # Video info label
        info_label = tk.Label(input_frame, textvariable=self.video_info_text, anchor='w', justify=tk.LEFT)
        info_label.grid(row=3, column=0, columnspan=3, sticky='w', pady=(5,0))

        input_frame.grid_columnconfigure(2, weight=1)

        # --- Model selection frame ---
        model_frame = tk.LabelFrame(controls_frame, text="Pose Model", padx=10, pady=10)
        model_frame.pack(pady=10, fill=tk.X, anchor='n')

        # This dropdown will be populated by the controller
        self.detector_dropdown = tk.OptionMenu(model_frame, self.selected_detector, "Loading...")
        self.detector_dropdown.pack(fill=tk.X)

        # --- Output settings frame ---
        output_frame = tk.LabelFrame(controls_frame, text="Output Settings", padx=10, pady=10)
        output_frame.pack(pady=10, fill=tk.X)

        # NDI Name
        ndi_label = tk.Label(output_frame, text="NDI Stream:")
        ndi_entry = tk.Entry(output_frame, textvariable=self.ndi_name)
        ndi_overlay_check = tk.Checkbutton(output_frame, text="Draw Overlay on NDI", variable=self.draw_ndi_overlay, command=self._on_ndi_overlay_change)
        self.btn_start_ndi = tk.Button(output_frame, text="Start", command=self.controller.start_ndi)
        self.btn_stop_ndi = tk.Button(output_frame, text="Stop", command=self.controller.stop_ndi, state=tk.DISABLED)

        ndi_label.grid(row=0, column=0, sticky="w", pady=2)
        ndi_entry.grid(row=1, column=0, columnspan=3, sticky="ew", pady=2)
        ndi_overlay_check.grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 5))
        self.btn_start_ndi.grid(row=3, column=1, sticky="ew")
        self.btn_stop_ndi.grid(row=3, column=2, sticky="ew")

        # OSC IP
        osc_ip_label = tk.Label(output_frame, text="OSC IP:")
        osc_ip_entry = tk.Entry(output_frame, textvariable=self.osc_ip)
        osc_ip_label.grid(row=4, column=0, sticky="w", pady=(10, 2))
        osc_ip_entry.grid(row=5, column=0, columnspan=3, sticky="ew", pady=2)

        # OSC Port
        osc_port_label = tk.Label(output_frame, text="OSC Port:")
        osc_port_entry = tk.Entry(output_frame, textvariable=self.osc_port)
        osc_port_label.grid(row=6, column=0, sticky="w", pady=2)
        osc_port_entry.grid(row=7, column=0, columnspan=3, sticky="ew", pady=2)

        # OSC Start/Stop Buttons
        self.btn_start_osc = tk.Button(output_frame, text="Start", command=self.controller.start_osc)
        self.btn_stop_osc = tk.Button(output_frame, text="Stop", command=self.controller.stop_osc, state=tk.DISABLED)
        self.btn_start_osc.grid(row=8, column=1, sticky="ew", pady=(5,0))
        self.btn_stop_osc.grid(row=8, column=2, sticky="ew", pady=(5,0))

        output_frame.grid_columnconfigure(0, weight=1)
        output_frame.grid_columnconfigure(1, weight=1)
        output_frame.grid_columnconfigure(2, weight=1)

    def on_closing(self):
        """Handle the window close event."""
        print("[GUI] Closing application...")
        self.controller.shutdown()
        self.root.destroy()

    def start_all(self):
        print("[GUI] 'Start All' button clicked. Calling controller...")
        self.controller.start_all()

    def start_video(self):
        print("[GUI] 'Start Video' button clicked. Calling controller...")
        self.controller.start()

    def pause_video(self):
        print("[GUI] 'Pause Video' button clicked. Calling controller...")
        self.controller.pause()

    def stop_video(self):
        print("[GUI] 'Stop Video' button clicked. Calling controller...")
        self.controller.stop_video_stream()

    def stop_all(self):
        print("[GUI] 'Stop All' button clicked. Calling controller...")
        self.controller.stop() # controller.stop() is the "stop all" function

    def _on_ndi_name_change(self, *args):
        self.controller.update_config('ndi_name', self.ndi_name.get())

    def _on_osc_ip_change(self, *args):
        self.controller.update_config('osc_ip', self.osc_ip.get())

    def _on_osc_port_change(self, *args):
        try:
            self.controller.update_config('osc_port', int(self.osc_port.get()))
        except (ValueError, TypeError): pass # Ignore invalid (e.g., empty) port values

    def _on_ndi_overlay_change(self):
        print("Change ndi overlay", self.draw_ndi_overlay.get())
        self.controller.update_config('draw_ndi_overlay', self.draw_ndi_overlay.get())

    def _on_source_change(self):
        """Called when a radio button is clicked."""
        source = self.input_source.get()
        self.controller.update_config('input', source)
        # The controller will call back to update_ui_config, which updates widget states

    def _update_input_widget_states(self):
        """Enables/disables input widgets based on the selected source."""
        is_webcam = self.input_source.get() == 'webcam'

        self.cam_dropdown.config(state=tk.NORMAL if is_webcam else tk.DISABLED)
        self.btn_file.config(state=tk.DISABLED if is_webcam else tk.NORMAL)
        # The file entry should follow the button's state, but remain readonly
        self.file_entry.config(state="readonly" if not is_webcam else tk.DISABLED)
        self.loop_check.config(state=tk.DISABLED if is_webcam else tk.NORMAL)

    def _on_loop_change(self):
        self.controller.update_config('loop_video', self.loop_video.get())

    def on_camera_select(self, selected_name):
        """Called when a user selects a camera from the dropdown."""
        # Update the StringVar to reflect the selection in the UI
        self.selected_camera.set(selected_name)

        camera_id = self.camera_map.get(selected_name)
        if camera_id is not None:
            self.controller.update_config("input", "webcam")
            self.controller.update_config("camera_id", camera_id)

    def update_camera_list(self, cameras):
        """Receives the camera list from the controller and populates the dropdown."""
        self.camera_map = {name: id for id, name in cameras.items()}
        menu = self.cam_dropdown['menu']
        menu.delete(0, 'end') # Clear existing options

        if not self.camera_map:
            self.cam_dropdown.config(state="disabled")
            self.selected_camera.set("No cameras found")
            return

        for name in self.camera_map.keys():
            # The command is re-bound for each new item
            menu.add_command(label=name, command=lambda value=name: self.on_camera_select(value))

        # Set default selection
        default_cam_id = self.controller.config['camera_id']
        default_cam_name = cameras.get(default_cam_id, list(cameras.values())[0])
        self.selected_camera.set(default_cam_name)
        self.cam_dropdown.config(state="normal")

    def select_file(self):
        file_path = filedialog.askopenfilename(title="Choose video file")
        if file_path:
            self.controller.update_config("input", "file")
            self.controller.update_config("video_file", file_path)

    def update_detector_list(self, detector_names, current_detector_name):
        """Receives the detector list from the controller and populates the dropdown."""
        menu = self.detector_dropdown['menu']
        menu.delete(0, 'end')

        for name in detector_names:
            menu.add_command(label=name, command=lambda value=name: self._on_detector_select(value))

        self.selected_detector.set(current_detector_name)

    def _on_detector_select(self, detector_name):
        self.controller.change_detector_model(detector_name)

    def update_ui_state(self, state):
        from core.controller import AppState # Local import to avoid circular dependency at module level
        self.root.title(f"PoseCam State: {state.name}")
        is_running = state == AppState.RUNNING
        is_stopped = state == AppState.STOPPED or state == AppState.READY
        is_paused = state == AppState.PAUSED

        # Determine button states
        start_enabled_state = tk.NORMAL if is_stopped else tk.DISABLED
        stop_enabled_state = tk.NORMAL if is_running or is_paused else tk.DISABLED
        pause_enabled_state = tk.NORMAL if is_running or is_paused else tk.DISABLED

        # Apply states to buttons
        self.btn_start_all.config(state=start_enabled_state)
        self.btn_stop_all.config(state=stop_enabled_state)
        self.btn_start.config(state=start_enabled_state)
        self.btn_stop.config(state=stop_enabled_state)

        # Disable detector selection while running
        self.detector_dropdown.config(state=tk.NORMAL if is_stopped else tk.DISABLED)

        # Update pause button to toggle text between "Pause" and "Continue"
        self.btn_pause.config(state=pause_enabled_state)
        if is_paused:
            self.btn_pause.config(text="Continue Video")
        else:
            self.btn_pause.config(text="Pause Video")

    def update_ndi_state(self, active):
        """Updates NDI button states based on controller feedback."""
        self.btn_start_ndi.config(state=tk.DISABLED if active else tk.NORMAL)
        self.btn_stop_ndi.config(state=tk.NORMAL if active else tk.DISABLED)

    def update_osc_state(self, active):
        """Updates OSC button states based on controller feedback."""
        self.btn_start_osc.config(state=tk.DISABLED if active else tk.NORMAL)
        self.btn_stop_osc.config(state=tk.NORMAL if active else tk.DISABLED)

    def update_ui_config(self, key, value):
        print(f"[GUI] Config {key} updated to {value}")
        if key == 'video_file':
            self.video_file_path.set(value or "")
        elif key == 'input':
            self.input_source.set(value)
            self._update_input_widget_states()
        elif key == 'draw_ndi_overlay':
            self.draw_ndi_overlay.set(value)
        elif key == 'detector_model':
            self.selected_detector.set(value)

    def update_video_info(self, width, height):
        """Updates the label with video resolution."""
        if width > 0 and height > 0:
            self.video_info_text.set(f"Input: {width}x{height}")
        else:
            self.clear_video_info()

    def clear_video_info(self):
        """Clears the video resolution label."""
        self.video_info_text.set("")

    def run(self):
        self._update_preview_loop()
        self.root.mainloop()

    def _update_preview_loop(self):
        """Checks the queue for a new frame and updates the canvas."""
        try:
            # Get current canvas dimensions
            canvas_w = self.preview_canvas.winfo_width()
            canvas_h = self.preview_canvas.winfo_height()

            # Don't process a frame until the canvas is ready (has a size).
            # This prevents consuming a frame from the queue before we can display it.
            if canvas_w <= 1 or canvas_h <= 1:
                return # Try again on the next loop cycle

            # Now that we know the canvas is ready, try to get a frame.
            frame = self.controller.preview_frame_queue.get_nowait()

            # If we got a frame, remove the initial "Waiting..." text
            if self.preview_canvas_text_id:
                print("[GUI] First frame received, displaying video.")
                self.preview_canvas.delete(self.preview_canvas_text_id)
                self.preview_canvas_text_id = None

            # --- Image Processing and Display ---
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)

            # Resize image to fit canvas while maintaining aspect ratio
            img.thumbnail((canvas_w, canvas_h), Image.Resampling.LANCZOS)
            self.preview_image = ImageTk.PhotoImage(image=img)

            # If the canvas image object doesn't exist, create it. Otherwise, update it.
            if self.preview_canvas_image_id is None:
                self.preview_canvas_image_id = self.preview_canvas.create_image(
                    canvas_w // 2, canvas_h // 2, anchor=tk.CENTER, image=self.preview_image)
            else:
                self.preview_canvas.itemconfig(self.preview_canvas_image_id, image=self.preview_image)

        except queue.Empty:
            pass  # No new frame, do nothing
        finally:
            # Schedule the next check
            self.root.after(30, self._update_preview_loop) # ~33fps poll rate