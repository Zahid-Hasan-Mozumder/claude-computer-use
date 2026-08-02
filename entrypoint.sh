#!/bin/bash
set -e

# 1. Start Xvfb Virtual Framebuffer on DISPLAY :1
echo "Starting Xvfb on DISPLAY :1 (1024x768x24)..."
Xvfb :1 -screen 0 1024x768x24 &
export DISPLAY=:1
sleep 2

# 2. Start lightweight Openbox Window Manager
echo "Starting Openbox window manager..."
openbox &
sleep 1

# 3. Start x11vnc VNC Server on port 5900
echo "Starting x11vnc server on port 5900..."
x11vnc -display :1 -forever -shared -rfbport 5900 -nopw &
sleep 1

# 4. Start noVNC Websockify proxy on port 6080
echo "Starting noVNC web proxy on port 6080..."
websockify --web=/usr/share/novnc 6080 localhost:5900 &
sleep 1

# 5. Start FastAPI Backend with Uvicorn
echo "Starting Computer Use FastAPI Backend on port 8000..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
