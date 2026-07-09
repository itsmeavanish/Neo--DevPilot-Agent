# =========================================================
# JARVIS - Autonomous Developer Operating System
# =========================================================
# Build: docker build -t jarvis .
# Run:   docker run -p 8000:8000 jarvis

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY src/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY run.py .

# Create non-root user
RUN useradd --create-home --shell /bin/bash jarvis && \
    chown -R jarvis:jarvis /app

USER jarvis

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/ || exit 1

# Run the application
CMD ["sh", "-c", "uvicorn jarvis.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
