# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    git \
    curl \
    libssl-dev \
    libffi-dev \
    python3-dev \
    libyaml-dev \
    && rm -rf /var/lib/apt/lists/*


# Install OpenCV dependencies ( Ubuntu 22.04 compatible headless)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libopenblas0 \
    liblapack3 \
    libgomp1 \
    libblas3 \
    # Image codecs (Ubuntu 22.04 versions) \
    libjpeg62-turbo \
    libpng16-16t64 \
    libtiff6 \
    libwebp7 \
    # Additional \
    zlib1g \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Non-root runtime user. Override APP_UID/APP_GID at build time to match
# the host user (e.g. `bridge`) so bind-mounted and named-volume paths
# (logs, tmp/uploads) are writable both from the host and the container
# without manual `chown` on the host after every deploy.
ARG APP_UID=1000
ARG APP_GID=1000
RUN (getent group ${APP_GID} || groupadd -g ${APP_GID} bridge) \
    && (getent passwd ${APP_UID} || useradd -u ${APP_UID} -g ${APP_GID} -m -s /bin/bash bridge)

# Create necessary directories with proper permissions
RUN mkdir -p \
    /app/certs \
    /app/logs \
    /app/tmp/uploads \
    && chown -R ${APP_UID}:${APP_GID} /app \
    && chmod 755 /app/logs \
    && chmod 755 /app/tmp/uploads

# Set proper permissions for certificates (if they exist in image)
# Note: These will be overridden by volume mounts in docker-compose
RUN if [ -f /app/certs/public.crt ]; then chmod 644 /app/certs/public.crt; fi && \
    if [ -f /app/certs/private.key ]; then chmod 600 /app/certs/private.key; fi

USER ${APP_UID}:${APP_GID}


# Expose port
EXPOSE 6443 6000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('https://localhost:6433/api/health', verify=False)" || exit 1

# Run application
CMD ["python", "-m", "server"]
