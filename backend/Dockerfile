# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Create necessary directories
RUN mkdir -p /app/certs /app/logs

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create upload directory
RUN mkdir -p /tmp/uploads

# Ensure proper permissions
RUN chmod 755 /app/logs

# Expose port
EXPOSE 6443

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('https://localhost:6433/api/health', verify=False)" || exit 1

# Run application
CMD ["python", "-m", "app.server"]
