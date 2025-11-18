import logging
import os
import traceback

from bicycleinit.device import BicycleDevice

def main():
  device = BicycleDevice()
  try:
    device.main()
  except Exception as e:
    logging.error(f"An unexpected error occurred: {e}")
    logging.error(traceback.format_exc())
  finally:
    logging.shutdown()
    if device._restart:
      return
    if os.path.exists('.no-shutdown'):
      logging.info("'.no-shutdown' file found, skipping shutdown.")
      return
    os.system("sudo shutdown now")

if __name__ == '__main__':
  main()
