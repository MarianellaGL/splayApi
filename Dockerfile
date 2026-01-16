# Splay Engine Docker Image
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY splay/ ./splay/
COPY pyproject.toml .

# Install package in editable mode
RUN pip install --no-cache-dir -e .

# Create cache directory
RUN mkdir -p /tmp/splay_cache

# Environment
ENV SPLAY_CACHE_DIR=/tmp/splay_cache
ENV SPLAY_ENV=production
ENV ALLOWED_ORIGINS=*

# Render sets PORT dynamically
EXPOSE 10000

# Start server
CMD ["sh", "-c", "uvicorn splay.api.app:app --host 0.0.0.0 --port ${PORT:-10000}"]
