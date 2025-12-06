# Build stage - use standard Python image with build tools
FROM python:3.11-slim AS builder

WORKDIR /build

# Install system dependencies needed for Pillow (used by reportlab)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    libtiff5-dev \
    libwebp-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/

# Install package and dependencies to a target directory
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --target=/app/packages .

# Runtime stage - use Python slim image (has libraries needed for Pillow)
FROM python:3.11-slim

# Install runtime libraries needed for Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo \
    zlib1g \
    libfreetype6 \
    liblcms2-2 \
    libopenjp2-7 \
    libtiff6 \
    libwebp7 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /app/packages /app/packages

# Copy source code
COPY --from=builder /build/src /app/src

# Set PYTHONPATH to include both packages and source
ENV PYTHONPATH=/app/packages:/app/src

# Set entrypoint - use python -m
ENTRYPOINT ["python", "-m", "vibanalyz.cli"]

