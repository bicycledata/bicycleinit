import logging
import subprocess
import time


def _run(command):
  try:
    result = subprocess.check_output(command, shell=True, text=True)
    return result.strip()
  except subprocess.CalledProcessError as e:
    return None

def turn_on():
  logging.info("Wifi on")
  return _run("sudo nmcli radio wifi on")

def turn_off():
  logging.info("Wifi off")
  return _run("sudo nmcli radio wifi off")

def connect(ssid, password=None):
  logging.info(f"Connecting to WiFi SSID: {ssid}")
  return _run(f"sudo nmcli dev wifi connect '{ssid}' password '{password}'")

def current_connection():
  return _run("nmcli -t -f active,ssid dev wifi | egrep '^yes' | cut -d: -f2")

def is_connected():
  return current_connection() is not None and current_connection() != ""

def scan_networks():
  result = _run("nmcli -t -f SSID dev wifi")
  if result:
    return [line for line in result.splitlines() if line]
  return []

def wait_for_network(ssids, timeout=30, interval=2):
  """
  Wait for any SSID in the list to appear. Returns the first found SSID, or None if none found within timeout.
  """
  while timeout > 0:
    available = scan_networks()
    for ssid in ssids:
      if ssid in available:
        return ssid
    time.sleep(interval)
    timeout -= interval
  return None
