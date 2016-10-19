#!/bin/sh
# run as root

cd /home/pi/floppy
lt -s floppyws -p 8000 &
python floppyplay.py
