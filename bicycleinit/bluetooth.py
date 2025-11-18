import logging
import subprocess


def _run(command):
  try:
    result = subprocess.check_output(command, shell=True, text=True)
    return result.strip()
  except subprocess.CalledProcessError as e:
    return None

def on():
  logging.info("Starting bluetooth service")
  return _run("sudo hciconfig hci0 up")

def off():
  logging.info("Stopping bluetooth service")
  return _run("sudo hciconfig hci0 down")

def status():
  # Check if bluetooth service is active
  service = _run("systemctl is-active bluetooth")
  if service != "active":
    logging.warning("Bluetooth service is not active.")
    return False

  # Check if adapter is present and powered
  adapter = _run("bluetoothctl show")
  if "Powered: yes" not in adapter:
    logging.warning("Bluetooth adapter is not powered on.")
    return False

  return True
