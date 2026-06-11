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
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libopenblas0 \
    liblapack3 \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p \
    /app/certs \
    /app/logs \
    /app/tmp/uploads \
    && chmod 755 /app/logs \
    && chmod 755 /app/tmp/uploads

# Set proper permissions for certificates (if they exist in image)
# Note: These will be overridden by volume mounts in docker-compose
RUN if [ -f /app/certs/public.crt ]; then chmod 644 /app/certs/public.crt; fi && \
    if [ -f /app/certs/private.key ]; then chmod 600 /app/certs/private.key; fi


# Expose port
EXPOSE 6443 6000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('https://localhost:6433/api/health', verify=False)" || exit 1

# Run application
CMD ["python", "-m", "server"]
