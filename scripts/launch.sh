#!/bin/bash -e

sudo ~/.klipper-status-led-env/bin/python ~/klipper-status-led/main.py -c ~/printer_data/config/status_led.cfg -s ~/printer_data/comms/klippy.sock -l ~/printer_data/logs/status_led.log