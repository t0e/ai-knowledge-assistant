FROM python:3.12-slim AS base

# Prevent Python from writing .pyc and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install system dependencies needed for compiling certain python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY apps/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy source code and configuration
COPY apps/api /app/apps/api

# Ensure entrypoint script is executable and create storage directory with permissions
RUN chmod +x /app/apps/api/entrypoint.sh && \
    mkdir -p /app/storage && \
    useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app /app/storage

USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/apps/api/entrypoint.sh"]
CMD ["uvicorn", "apps.api.src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
