import logging
import os
import signal
import sys
import threading
import time
from collections import deque
from datetime import UTC, datetime
from multiprocessing.connection import Connection


class BicycleSensor:
    def __init__(self, bicycleinit: Connection, name: str, args: dict):
        self._bicycleinit = bicycleinit
        self._name = name

        self._min_msgs = args.get("min_msgs", 5)
        self._session = args["session"]
        self._time_frame = args.get("time_frame", 10)  # seconds
        self._upload_interval = args.get("upload_interval", 60)

        self._temp_path = os.path.join("temp", self._session)
        self._target_path = os.path.join("sessions", self._session)
        self._filename = None
        self._file = None

        self._send_lock = threading.Lock()
        self.send_msg({"type": "log", "level": "info", "msg": "Starting sensor " + self._name})

        # Register signal handlers for safe shutdown
        signal.signal(signal.SIGTERM, self._handle_exit)
        signal.signal(signal.SIGINT, self._handle_exit)

        # Event for clean shutdown of background thread
        self._shutdown_event = threading.Event()

        # Start background thread for file creation
        self._thread = threading.Thread(target=self._background_file_creator, daemon=True)
        self._thread.start()

        # Start background thread for pinging
        self._ping_lock = threading.Lock()
        self._pings = deque()
        self._ping_thread = threading.Thread(target=self._background_pinger, daemon=True)
        self._ping_thread.start()

    def ping(self):
        with self._ping_lock:
            self._pings.append(time.monotonic())

    def send_msg(self, msg):
        if self._bicycleinit is None:
            logging.info(f"[{self._name}] {msg}")
            return

        with self._send_lock:
            if isinstance(msg, dict):
                self._bicycleinit.send(msg)
            else:
                self._bicycleinit.send({"type": "log", "level": "info", "msg": str(msg)})

    def _background_file_creator(self):
        while not self._shutdown_event.is_set():
            # Wait for the interval or until shutdown is triggered
            self._shutdown_event.wait(timeout=self._upload_interval)
            if self._shutdown_event.is_set():
                self.close_file()
            else:
                self.open_file()

    def _background_pinger(self):
        status = "init"

        while not self._shutdown_event.is_set():
            # Wait for 1s or until shutdown is triggered
            self._shutdown_event.wait(timeout=1)
            if self._shutdown_event.is_set():
                break

            with self._ping_lock:
                now = time.monotonic()

                # Remove old timestamps
                while self._pings and now - self._pings[0] > self._time_frame:
                    self._pings.popleft()

                # Check online status
                new_status = "online" if len(self._pings) >= self._min_msgs else "offline"

            if new_status != status:
                status = new_status
                self.send_msg({"type": "status", "status": status})

    def _handle_exit(self, signum, frame):
        self._shutdown_event.set()
        self._thread.join(timeout=5)
        self._ping_thread.join(timeout=5)
        self.close_file()
        self.send_msg(
            {
                "type": "log",
                "level": "info",
                "msg": f"Sensor is shutting down due to signal {signum} with frame {frame}",
            }
        )
        if self._bicycleinit is not None:  # internal sensors set self._bicycleinit to None, i.e. bicyclebutton
            sys.exit(0)

    def write_header(self, headers):
        if self._file is None:
            self.open_file()
        self._file.write("time," + ",".join(headers) + "\n")

    def write_measurement(self, data):
        if self._file is None:
            self.open_file()
        ts = datetime.now(UTC).isoformat()
        data = [str(x) for x in data]
        if float(data[0]) > 10.0:  # data[0] is duration
            self.send_msg(
                {
                    "type": "log",
                    "level": "info",
                    "msg": f"User held button for over 10s. Proceeding to upload and shut down.",
                }
            )
            return  # do not record this button press
        self._file.write(ts + "," + ",".join(data) + "\n")
        self.ping()

    def close_file(self):
        if self._file is None:
            return
        self._file.close()
        self.send_msg({"type": "upload", "file": self._filename})
        self._filename = None
        self._file = None

    def open_file(self):
        self.close_file()

        now = datetime.now(UTC)
        self._filename = now.strftime("%Y%m%d-%H%M%S") + "-" + self._name
        self._file = open(os.path.join(self._temp_path, self._filename), "w")

    def shutdown(self):
        self._handle_exit(signal.SIGTERM, None)
