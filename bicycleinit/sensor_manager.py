import importlib
import threading
import time
from multiprocessing import Pipe, Process, connection

SENSOR_LOCK = threading.Lock()

SENSOR_PROCESSES: dict[str, Process] = {}
SENSOR_CONNS = {}


def start_sensor(name, module, main, args):
    with SENSOR_LOCK:
        sensor_module = importlib.import_module(module)
        sensor_main = getattr(sensor_module, main)

        parent_conn, child_conn = Pipe()
        p = Process(target=sensor_main, args=(child_conn, name, args))
        p.start()
        SENSOR_CONNS[name] = parent_conn
        SENSOR_PROCESSES[name] = p


def kill_sensors():
    with SENSOR_LOCK:
        for p in SENSOR_PROCESSES.values():
            p.terminate()
