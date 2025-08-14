"""
camera_utils.py

Utility for enumerating available camera input devices on Windows using DirectShow.
Returns a dictionary that maps OpenCV device index to user-friendly device name.
Used to populate dropdown menus or camera selection UIs in PoseCamPC.
"""

from pygrabber.dshow_graph import FilterGraph

def get_available_cameras():
    """
    Returns:
        dict: Mapping of integer camera IDs (as used by OpenCV) to string names.
    Example:
        {
            0: 'Integrated Webcam',
            1: 'USB Video Device',
            2: 'NDI Virtual Input'
        }
    """
    devices = FilterGraph().get_input_devices()
    return {i: name for i, name in enumerate(devices)}

# Uncomment for quick standalone test:
# print(get_available_cameras())
