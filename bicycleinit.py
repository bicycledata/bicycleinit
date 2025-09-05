import logging
import os
import traceback

from bicycleinit.device import BicycleDevice

if __name__ == '__main__':
  device = BicycleDevice()
  try:
    device.main()
  except Exception as e:
    logging.error(f"An unexpected error occurred: {e}")
    logging.error(traceback.format_exc())
  finally:
    logging.shutdown()
    os.system("sudo shutdown now")
