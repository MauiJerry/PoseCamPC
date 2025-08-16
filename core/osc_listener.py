from pythonosc import dispatcher, osc_server
import logging

class OSCListener:
    def __init__(self, controller):
        self.controller = controller
        self.server = None

    def start(self):
        disp = dispatcher.Dispatcher()
        disp.map("/posecam/control/start", self.handle_start)
        disp.map("/posecam/control/stop", self.handle_stop)
        disp.map("/posecam/control/pause", self.handle_pause)
        disp.map("/posecam/input/select", self.handle_input_select)
        disp.map("/posecam/input/file", self.handle_file_select)
        disp.map("/posecam/output/osc/ip", self.handle_osc_ip)
        disp.map("/posecam/output/osc/port", self.handle_osc_port)
        
        listen_port = self.controller.config['osc_listen_port']
        self.server = osc_server.ThreadingOSCUDPServer(("0.0.0.0", listen_port), disp)
        print(f"[OSC] Listener starting, listening on port {listen_port}...")
        self.server.serve_forever()

    def shutdown(self):
        if self.server:
            print("[OSC] Shutting down listener...")
            self.server.shutdown()
            self.server.server_close()
            self.server = None
            print("[OSC] Listener shut down.")

    def handle_start(self, addr, *args):
        self.controller.start()

    def handle_stop(self, addr, *args):
        self.controller.stop()

    def handle_pause(self, addr, *args):
        self.controller.pause()

    def handle_input_select(self, addr, source):
        self.controller.update_config('input', source)

    def handle_file_select(self, addr, path):
        self.controller.update_config('video_file', path)

    def handle_osc_ip(self, addr, ip):
        self.controller.update_config('osc_ip', ip)

    def handle_osc_port(self, addr, port):
        self.controller.update_config('osc_port', int(port))