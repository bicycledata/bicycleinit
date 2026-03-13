import datetime
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from multiprocessing import connection

from bicycleinit import (
    api,
    bicyclebutton,
    bluetooth,
    boxui,
    sensor_manager,
    upgrade,
    wifi,
)


def file_hash(path):
    """Return SHA256 hash of the file contents."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class BicycleDevice:
    def __init__(self):
        time.sleep(2)  # Wait a bit for system services to be ready

        self._restart = True

        # Create the session name based on date and time
        self.session = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d-%H%M%S")
        self.session_dir = os.path.join("sessions", self.session)
        self.temp_dir = os.path.join("temp", self.session)

        os.makedirs(self.session_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)

        logging.basicConfig(
            filename=os.path.join(self.session_dir, "bicycleinit.log"),
            level=logging.INFO,
            format="[%(asctime)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
            force=True,
        )
        logging.Formatter.converter = lambda *args: datetime.datetime.now(datetime.UTC).timetuple()

        logging.info(f"Session name: {self.session}")
        logging.info(f"Executable: {sys.executable}")
        logging.info(f"Arguments: {sys.argv}")
        logging.info(f"Working directory: {os.getcwd()}/")
        logging.info(f"Python version: {sys.version.replace(chr(10), ' ')}")
        logging.info(f"Timestamp (UTC): {datetime.datetime.now(datetime.UTC).isoformat()}")

        boxui.init()
        boxui.blink()

    def move_all_pending_files(self):
        sessions = [name for name in os.listdir("temp") if os.path.isdir(os.path.join("temp", name))]
        for session in sessions:
            try:
                # move all files from temp/session to sessions/session
                os.makedirs(os.path.join("sessions", session), exist_ok=True)
                files = [
                    name
                    for name in os.listdir(os.path.join("temp", session))
                    if os.path.isfile(os.path.join("temp", session, name))
                ]
                for file in files:
                    shutil.move(os.path.join("temp", session, file), os.path.join("sessions", session, file))
                if session != self.session:
                    os.rmdir(os.path.join("temp", session))
                logging.info(f"Moved pending files from temp/{session} to sessions/{session}")
            except Exception as e:
                logging.error(f"Failed to move pending files for session {session}: {e}")

    def start_wifi(self, ssids, config):
        wifi.turn_on()
        ssid = wifi.wait_for_network(ssids, timeout=30)

        if ssid is None:
            # No configured SSID found
            logging.warning("No configured SSID found within timeout")
            self.stop_wifi()
            return

        # Connect to the found SSID
        logging.info(f"Found configured SSID: {ssid}, attempting to connect")
        wifi.connect(ssid, config["wifi"][ssid])

        if wifi.is_connected():
            boxui._LED1.on()
        else:
            self.stop_wifi()

    def stop_wifi(self):
        wifi.turn_off()
        boxui._LED1.off()

    def main(self):
        # Load configuration
        config_path = "bicycleinit.json" if os.path.exists("bicycleinit.json") else "bicycleinit-default.json"
        with open(config_path, "r") as f:
            config = json.load(f)
        logging.info(f"Loaded config: {config_path}")

        logging.info(f"Server: {config['server']}")

        # make a list of all ssids in config
        ssids = config["wifi"].keys()
        logging.info(f"Configured SSIDs: {list(ssids)}")

        # LED1 indicates WiFi connection status
        # LED2 indicates GPS status
        # LED3 indicates Radar status

        # Enable wifi
        time.sleep(1)
        bluetooth.off()
        time.sleep(1)
        self.start_wifi(ssids, config)

        api.time(config["server"])

        # If not registered, register the device
        if "registration" not in config:
            try:
                logging.info("Device not registered, attempting registration...")
                api.register(config["server"])
            except Exception as e:
                logging.error(f"Registration failed: {e}")
                boxui.off()
            finally:
                return  # Exit to allow a restart by systemd or similar

        # Try to fetch a new bicycleinit.json
        try:
            old_hash = file_hash("bicycleinit.json")
            api.config(config["server"], config["ident"])
            new_hash = file_hash("bicycleinit.json")

            # copy bicycleinit.json to session folder
            shutil.copyfile("bicycleinit.json", os.path.join(self.session_dir, "bicycleinit.json"))

            if old_hash != new_hash:
                logging.info("Restarting to apply new configuration (bicycleinit.json)...")
                boxui.off()
                return  # Exit to allow a restart by systemd or similar
            else:
                logging.info("bicycleinit.json was already up to date.")
        except Exception as e:
            logging.error(f"Failed to fetch updated configuration: {e}")

        # upload all pending session data
        # doing it not earlier, to get potential warnings/errors in the new log file
        self.move_all_pending_files()
        api.upload_pending(config["ident"], config["server"], self.session, True)

        # Try to upgrade from git
        if "branch" in config:
            upgrade_needed = upgrade.upgrade(config["branch"])
            if upgrade_needed:
                boxui.off()
                return  # Exit to allow a restart by systemd or similar
        else:
            logging.info("'branch' not defined in config file; Skipping pulling updates form git")

        # Setup sensor repos
        os.makedirs("sensors", exist_ok=True)
        sensors = config.get("sensors", [])
        for sensor in sensors:
            upgrade.clone_or_pull_repo(
                sensor["git_url"], os.path.join("sensors", sensor["name"]), sensor.get("git_branch", "main")
            )
            # if requirements.txt exists, install it
            req_path = os.path.join("sensors", sensor["name"], "requirements.txt")
            if os.path.exists(req_path):
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_path])
                    logging.info(f"Installed requirements for {sensor['name']} from {req_path}")
                except Exception as e:
                    logging.error(f"Failed to install requirements for {sensor['name']} from {req_path}: {e}")

        self.stop_wifi()  # Disable WiFi to save power until needed again

        time.sleep(1)
        bluetooth.on()
        time.sleep(1)
        bluetooth.status()

        # Run all sensors in their own process
        for sensor in sensors:
            file, fcn = sensor["entry_point"].split(":")
            sensor["args"]["session"] = self.session
            sensor_manager.start_sensor(sensor["name"], "sensors." + sensor["name"] + "." + file, fcn, sensor["args"])

        bicyclebutton.start_bicyclebutton(
            "bicyclebutton", {"session": self.session, "gpio": 23, "upload_interval": 300}
        )

        while True:
            # Wait for any connection to become ready
            ready_conns = connection.wait(sensor_manager.SENSOR_CONNS.values())

            with sensor_manager.SENSOR_LOCK:
                for conn in ready_conns:
                    # Find which sensor this connection belongs to
                    sensor_name = next(name for name, c in sensor_manager.SENSOR_CONNS.items() if c == conn)

                    try:
                        msg = conn.recv()
                        if sensor_name == "bicyclebutton" and "Proceeding to upload and shutdown." in msg:
                            boxui.shutdown()  # shutdown all othe sensors too

                    except EOFError:
                        conn.close()
                        sensor_manager.SENSOR_CONNS.pop(sensor_name)
                        logging.info(f"[{sensor_name}] Sensor terminated")

                        if not sensor_manager.SENSOR_CONNS:
                            boxui.blink_fast()
                            logging.info("All sensors terminated - shutting down")
                            bicyclebutton.stop_bicyclebutton()
                            time.sleep(1)
                            bluetooth.off()
                            time.sleep(1)
                            self.start_wifi(ssids, config)
                            try:
                                self.move_all_pending_files()
                                api.upload_pending(config["ident"], config["server"], self.session, False)
                            except Exception as e:
                                logging.error(f"shutdown: Final upload failed: {e}")
                            boxui.off()
                            self._restart = False
                            return
                    else:
                        if msg["type"] == "upload":
                            try:
                                shutil.move(
                                    os.path.join(self.temp_dir, msg["file"]),
                                    os.path.join(self.session_dir, msg["file"]),
                                )
                            except Exception as e:
                                logging.error(
                                    f"[{sensor_name}] Failed to move file {msg['file']} to session folder: {e}"
                                )
                        elif msg["type"] == "status":
                            logging.info(f"[{sensor_name}] {msg}")
                            if sensor_name == "bicyclegps":
                                boxui._LED2.on() if msg["status"] == "online" else boxui._LED2.off()
                            if sensor_name == "bicycleradar":
                                boxui._LED3.on() if msg["status"] == "online" else boxui._LED3.off()
                        elif msg["type"] == "log":
                            if "level" in msg and msg["level"] == "info":
                                logging.info(f"[{sensor_name}] {msg['msg']}")
                            elif "level" in msg and msg["level"] == "warning":
                                logging.warning(f"[{sensor_name}] {msg['msg']}")
                            elif "level" in msg and msg["level"] == "error":
                                logging.error(f"[{sensor_name}] {msg['msg']}")
                            else:
                                logging.info(f"[{sensor_name}] {msg}")
                        else:
                            logging.warning(f"Unknown message type from {sensor_name}: {msg}")
