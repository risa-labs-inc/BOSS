# Dockerfile for BOSS Monitoring Service
# Multi-stage build for a smaller final image

# Build stage
FROM python:3.10-slim AS builder

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy only the files needed for installation
COPY pyproject.toml poetry.lock ./

# Configure poetry to not use a virtual environment
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --no-dev --no-interaction --no-ansi

# Runtime stage
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy Python dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the application code
COPY boss ./boss
COPY scripts ./scripts

# Create directory for monitoring data
RUN mkdir -p /app/monitoring_data

# Set environment variables
ENV PYTHONPATH=/app
ENV MONITORING_DATA_DIR=/app/monitoring_data
ENV HOST=0.0.0.0
ENV PORT=8080

# Expose the monitoring API port
EXPOSE 8080

# Run the monitoring service
CMD ["python", "-m", "boss.lighthouse.monitoring.start_monitoring", \
     "--data-dir", "${MONITORING_DATA_DIR}", \
     "--host", "${HOST}", \
     "--port", "${PORT}"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1 