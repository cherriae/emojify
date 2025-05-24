#!/bin/bash

# Kill any running Python processes
sudo pkill -f python
sudo pkill -f python3
sudo pkill -f py

# Kill any libcamera processes
sudo pkill -f libcamera

# Wait for camera to reset
sleep 1

# Run Application
python3 app.py