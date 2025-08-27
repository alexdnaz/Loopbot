# Use official Python base image
FROM python:3.12-slim

# Cache bust to force reinstallation of system dependencies
ARG CACHEBUST=1
# Install system dependencies for scripts (jq, curl, openssl)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      bash \
      curl \
      jq \
      openssl \
      fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy Python requirements and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .


# Default command
CMD ["python", "LoopBot/bot.py"]
