import logging
import os
import signal
import sys
import threading
from datetime import UTC, datetime
from multiprocessing.connection import Connection


class BicycleSensor:
  def __init__(self, bicycleinit : Connection, name : str, args : dict):
    self._bicycleinit = bicycleinit
    self._name = name
    self._args = args
    self._session = self._args['session']

    self._temp_path = os.path.join('temp', self._session)
    self._target_path = os.path.join('sessions', self._session)
    self._filename = None
    self._file = None

    self._send_lock = threading.Lock()
    self.send_msg({'type': 'log', 'level': 'info', 'msg': "Starting sensor " + self._name})

    # Register signal handlers for safe shutdown
    signal.signal(signal.SIGTERM, self._handle_exit)
    signal.signal(signal.SIGINT, self._handle_exit)

    # Event for clean shutdown of background thread
    self._shutdown_event = threading.Event()

    # Start background thread for file creation
    self._thread = threading.Thread(target=self._background_file_creator, daemon=True)
    self._thread.start()

  def send_msg(self, msg):
    if self._bicycleinit is None:
      logging.info(f'[{self._name}] {msg}')
      return

    with self._send_lock:
      if isinstance(msg, dict):
        self._bicycleinit.send(msg)
      else:
        self._bicycleinit.send({'type': 'log', 'level': 'info', 'msg': str(msg)})

  def _background_file_creator(self):
    upload_interval = self._args.get('upload_interval', 60)
    while not self._shutdown_event.is_set():
      # Wait for the interval or until shutdown is triggered
      self._shutdown_event.wait(timeout=upload_interval)
      if self._shutdown_event.is_set():
        self.close_file()
      else:
        self.open_file()

  def _handle_exit(self, signum, frame):
    self._shutdown_event.set()
    self._thread.join(timeout=5)
    self.close_file()
    self.send_msg({'type': 'log', 'level': 'info', 'msg': f"Sensor is shutting down due to signal {signum}"})
    if self._bicycleinit is not None:
      sys.exit(0)

  def write_header(self, headers):
    if self._file is None:
      self.open_file()
    self._file.write('time,' + ','.join(headers) + '\n')

  def write_measurement(self, data):
    if self._file is None:
      self.open_file()
    ts = datetime.now(UTC).isoformat()
    data = [str(x) for x in data]
    self._file.write(ts + ',' + ','.join(data) + '\n')

  def close_file(self):
    if self._file is None:
      return
    self._file.close()
    self.send_msg({'type': 'upload', 'file': self._filename})
    self._filename = None
    self._file = None

  def open_file(self):
    self.close_file()

    now = datetime.now(UTC)
    self._filename = now.strftime('%Y%m%d-%H%M%S') + '-' + self._name
    self._file = open(os.path.join(self._temp_path, self._filename), 'w')

  def shutdown(self):
    self._handle_exit(signal.SIGTERM, None)
