FROM python:3.12-slim

# Qt (xcb) runtime, PortAudio with the ALSA->Pulse route, and fonts.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libegl1 libxkbcommon0 libxkbcommon-x11-0 libdbus-1-3 \
    libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 \
    libxcb-render-util0 libxcb-image0 libxcb-randr0 libxcb-xinerama0 \
    libfontconfig1 libfreetype6 fonts-dejavu-core \
    libasound2 libasound2-plugins libportaudio2 \
    && rm -rf /var/lib/apt/lists/*

# Route ALSA's default device to the PulseAudio server named in PULSE_SERVER,
# which the compose file points at the host (host.docker.internal).
RUN printf 'pcm.!default { type pulse }\nctl.!default { type pulse }\n' > /etc/asound.conf

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pytest ruff

COPY pyproject.toml .
COPY src ./src
COPY tests ./tests

ENV PYTHONPATH=/app/src
CMD ["python", "-m", "penmixer.app"]
