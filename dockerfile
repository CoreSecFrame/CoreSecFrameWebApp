# Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV FLASK_APP run.py
ENV FLASK_ENV production

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tmux \
    git \
    curl \
    sudo \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -s /bin/bash -m appuser && \
    echo "appuser ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/appuser

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy project
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p /app/logs /app/modules /app/instance && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Run gunicorn
CMD gunicorn --bind 0.0.0.0:5000 "run:app"