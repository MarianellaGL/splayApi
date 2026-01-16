# Splay Engine Docker Image
# For deployment on Render and other container platforms

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY pyproject.toml .
COPY splay/ ./splay/

# Install the package
RUN pip install --no-cache-dir -e .

# Create cache directory
RUN mkdir -p /tmp/splay_cache

# Default environment variables
ENV SPLAY_CACHE_DIR=/tmp/splay_cache
ENV SPLAY_ENV=production
ENV ALLOWED_ORIGINS=*
ENV PORT=8000

# Expose the port (Render sets PORT dynamically)
EXPOSE $PORT

# Run the API server
# Note: Render sets $PORT automatically
CMD uvicorn splay.api.app:app --host 0.0.0.0 --port ${PORT:-8000}
