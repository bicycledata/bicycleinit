import logging

from gpiozero import LED, Button

from bicycleinit import sensor_manager

_LED1 = None
_LED2 = None
_LED3 = None
_BUTTON = None


def init():
    global _LED1, _LED2, _LED3, _BUTTON
    _LED1 = LED(16)
    _LED2 = LED(20)
    _LED3 = LED(21)

    _BUTTON = Button(12, hold_time=5)
    _BUTTON.when_held = shutdown


def off():
    global _LED1, _LED2, _LED3
    _LED1.off()
    _LED2.off()
    _LED3.off()


def blink():
    global _LED1, _LED2, _LED3
    _LED1.blink(on_time=0.2, off_time=0.6)
    _LED2.blink(on_time=0.2, off_time=0.6)
    _LED3.blink(on_time=0.2, off_time=0.6)


def blink_fast():
    global _LED1, _LED2, _LED3
    _LED1.blink(on_time=0.2, off_time=0.2)
    _LED2.blink(on_time=0.2, off_time=0.2)
    _LED3.blink(on_time=0.2, off_time=0.2)


def shutdown():
    logging.info("Button held for 5 seconds. Shutting down...")
    blink_fast()
    sensor_manager.kill_sensors()
