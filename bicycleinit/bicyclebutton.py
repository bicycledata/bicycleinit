import time

from gpiozero import Button

from bicycleinit.BicycleSensor import BicycleSensor

_sensor = None
_press_time = None
_button = None

def on_press():
  global _press_time
  _press_time = time.time()

def on_release():
  global _sensor, _press_time
  if _press_time is not None:
    duration = time.time() - _press_time
    _press_time = None
    _sensor.write_measurement([duration])

def start_bicyclebutton(name: str, args: dict):
  global _sensor, _press_time, _button
  _sensor = BicycleSensor(None, name, args)

  _press_time = None

  port = args.get('gpio', 23)
  _button = Button(port)

  _sensor.write_header(['duration'])
  _button.when_released = on_release
  _button.when_pressed = on_press

def stop_bicyclebutton():
  global _sensor, _button
  _button.close()
  _sensor.shutdown()
