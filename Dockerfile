# ── Sécur'Âge dev image ────────────────────────────────────────────────────────
FROM python:3.12-slim

# ── Environnement de base ──────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ── Dépendances système OpenCV / YOLO ──────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 \
    libgstreamer1.0-0 libgstreamer-plugins-base1.0-0 libgtk-3-0 \
    libavcodec-dev libavformat-dev libswscale-dev libv4l-dev \
    libjpeg-dev libpng-dev libtiff-dev libatlas-base-dev gfortran \
    curl git && \
    rm -rf /var/lib/apt/lists/*

# ── Poetry 2.1 (PEP 621) ───────────────────────────────────────────────────────
ARG POETRY_VERSION=2.1.0
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

# 🔑  Désactive la création de virtual-envs
RUN poetry config virtualenvs.create false

WORKDIR /app

# ── Fichiers de dépendances ────────────────────────────────────────────────────
COPY pyproject.toml poetry.lock ./
RUN --mount=type=cache,target=/root/.cache \
    poetry install --no-ansi --no-interaction --no-root

# ── Code source ────────────────────────────────────────────────────────────────
COPY . .

# Dossiers runtime
RUN mkdir -p media/snapshots media/clips

EXPOSE 8000

# ── Commande de démarrage ──────────────────────────────────────────────────────
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
