# Build stage - use standard Python image with build tools
FROM python:3.11-slim AS builder

WORKDIR /build

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/

# Install package and dependencies to a target directory
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --target=/app/packages .

# Runtime stage - use minimal Chainguard image
FROM cgr.dev/chainguard/python:latest

# Copy installed packages from builder
COPY --from=builder /app/packages /app/packages

# Copy source code
COPY --from=builder /build/src /app/src

# Set PYTHONPATH to include both packages and source
ENV PYTHONPATH=/app/packages:/app/src

# Set entrypoint - use python -m with the Chainguard Python
ENTRYPOINT ["python", "-m", "vibanalyz.cli"]

