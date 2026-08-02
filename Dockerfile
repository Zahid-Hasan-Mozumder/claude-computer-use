FROM python:3.12-slim-bookworm

# Prevent python from writing pyc files and buffer output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:1

# Install system dependencies for X11, VNC, noVNC, and GUI tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    xdotool \
    scrot \
    x11vnc \
    openbox \
    novnc \
    websockify \
    net-tools \
    curl \
    git \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy project configuration and sync dependencies
COPY pyproject.toml README.md ./
COPY app ./app
COPY main.py ./

RUN uv pip install --system .

# Copy entrypoint script
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Expose FastAPI (8000), noVNC (6080), RFB VNC (5900)
EXPOSE 8000 6080 5900

# Container entrypoint
ENTRYPOINT ["./entrypoint.sh"]
