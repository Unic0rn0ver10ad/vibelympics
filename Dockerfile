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

# Install runtime libraries needed for Pillow and tools for Syft
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo \
    zlib1g \
    libfreetype6 \
    liblcms2-2 \
    libopenjp2-7 \
    libtiff6 \
    libwebp7 \
    curl \
    tar \
    && rm -rf /var/lib/apt/lists/*

# Install Syft CLI
RUN SYFT_VERSION=$(curl -s https://api.github.com/repos/anchore/syft/releases/latest | grep '"tag_name":' | sed -E 's/.*"v([^"]+)".*/\1/') && \
    curl -LO https://github.com/anchore/syft/releases/download/v${SYFT_VERSION}/syft_${SYFT_VERSION}_linux_amd64.tar.gz && \
    tar -xzf syft_${SYFT_VERSION}_linux_amd64.tar.gz && \
    mv syft /usr/local/bin/syft && \
    chmod +x /usr/local/bin/syft && \
    rm -f syft_${SYFT_VERSION}_linux_amd64.tar.gz && \
    syft version

# Copy installed packages from builder
COPY --from=builder /app/packages /app/packages

# Copy source code
COPY --from=builder /build/src /app/src

# Set PYTHONPATH to include both packages and source
ENV PYTHONPATH=/app/packages:/app/src

# Set entrypoint - use python -m
ENTRYPOINT ["python", "-m", "vibanalyz.cli"]
