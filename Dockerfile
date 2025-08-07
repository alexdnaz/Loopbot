# Use official Python base image
FROM python:3.12-slim

# Install system dependencies for scripts (jq, curl, openssl)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      bash \
      curl \
      jq \
      openssl \
 && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy Python requirements and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure our helper is executable
RUN chmod +x ./scripts/spotify.sh

# Default command
CMD ["python", "bot.py"]
