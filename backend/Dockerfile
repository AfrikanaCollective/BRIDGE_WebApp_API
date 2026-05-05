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

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create necessary directories
RUN mkdir -p /app/certs /app/logs /app/uploads /tmp

# Ensure proper permissions
RUN chmod 755 /app/logs

# Expose port
EXPOSE 6443 6000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('https://localhost:6433/api/health', verify=False)" || exit 1

# Run application
CMD ["python", "-m", "app.server"]
