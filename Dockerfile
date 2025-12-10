# Build stage - use Chainguard Python dev image with build tools
FROM cgr.dev/chainguard/python:latest-dev AS builder

# Switch to root for package installation
USER root

RUN echo "🔨 Starting build stage..."

WORKDIR /build

# Install system dependencies needed for Pillow (used by reportlab)
# Chainguard images use apk (Wolfi/Alpine package manager)
RUN echo "📦 Installing build dependencies (Pillow/image libraries)..." && \
    apk add --no-cache \
    libjpeg-turbo-dev \
    zlib-dev \
    freetype-dev \
    lcms2-dev \
    openjpeg-dev \
    tiff-dev \
    libwebp-dev

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/

# Install package and dependencies to a target directory
RUN echo "🐍 Installing Python packages and dependencies..." && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --target=/app/packages .

# Runtime stage - use Chainguard Python dev image (needed for runtime libs and Syft installation)
FROM cgr.dev/chainguard/python:latest-dev

# Switch to root for package installation
USER root

RUN echo "🚀 Starting runtime stage..."

# Install runtime libraries needed for Pillow and tools for Syft
# Using latest-dev variant to have apk available for installing runtime dependencies
RUN echo "📚 Installing runtime libraries and build tools..." && \
    apk add --no-cache \
    libjpeg-turbo \
    zlib \
    freetype \
    lcms2 \
    openjpeg \
    tiff \
    libwebp \
    curl \
    nodejs \
    npm \
    gcc \
    openssl-dev

# Install Rust and Cargo using rustup (official Rust installer)
# Chainguard/Wolfi doesn't have rust/cargo packages, so we use rustup
# Copy binaries to /usr/local/bin so they're accessible to all users (including nonroot)
RUN echo "🦀 Installing Rust toolchain (this may take a minute)..." && \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable --profile minimal && \
    /root/.cargo/bin/rustup --version && \
    /root/.cargo/bin/cargo --version && \
    # Copy cargo, rustc, and rustup binaries to /usr/local/bin (not symlinks)
    # This ensures they're accessible to nonroot user
    cp /root/.cargo/bin/cargo /usr/local/bin/cargo && \
    cp /root/.cargo/bin/rustc /usr/local/bin/rustc && \
    cp /root/.cargo/bin/rustup /usr/local/bin/rustup && \
    # Ensure binaries are executable by all users
    chmod +x /usr/local/bin/cargo /usr/local/bin/rustc /usr/local/bin/rustup

# Install Syft CLI
# Use Python's tarfile module to extract since tar package may not be available
RUN echo "📋 Installing Syft CLI (SBOM generation tool)..." && \
    SYFT_VERSION=$(curl -s https://api.github.com/repos/anchore/syft/releases/latest | grep '"tag_name":' | sed -E 's/.*"v([^"]+)".*/\1/') && \
    curl -LO https://github.com/anchore/syft/releases/download/v${SYFT_VERSION}/syft_${SYFT_VERSION}_linux_amd64.tar.gz && \
    python3 -c "import tarfile; tarfile.open('syft_${SYFT_VERSION}_linux_amd64.tar.gz').extractall()" && \
    mv syft /usr/local/bin/syft && \
    chmod +x /usr/local/bin/syft && \
    rm -f syft_${SYFT_VERSION}_linux_amd64.tar.gz && \
    syft version

# Install Grype CLI
# Use Python's tarfile module to extract since tar package may not be available
RUN echo "🔍 Installing Grype CLI (vulnerability scanner)..." && \
    GRYPE_VERSION=$(curl -s https://api.github.com/repos/anchore/grype/releases/latest | grep '"tag_name":' | sed -E 's/.*"v([^"]+)".*/\1/') && \
    curl -LO https://github.com/anchore/grype/releases/download/v${GRYPE_VERSION}/grype_${GRYPE_VERSION}_linux_amd64.tar.gz && \
    python3 -c "import tarfile; tarfile.open('grype_${GRYPE_VERSION}_linux_amd64.tar.gz').extractall()" && \
    mv grype /usr/local/bin/grype && \
    chmod +x /usr/local/bin/grype && \
    rm -f grype_${GRYPE_VERSION}_linux_amd64.tar.gz && \
    grype version

# Copy installed packages from builder
COPY --from=builder /app/packages /app/packages

# Copy source code
COPY --from=builder /build/src /app/src

# Create output directory for reports and SBOMs
RUN echo "📁 Setting up application directories and permissions..." && \
    mkdir -p /app/output && \
    chown -R nonroot:nonroot /app/packages /app/src /app/output

# Switch back to non-root user for security (Chainguard default is nonroot:65532)
USER nonroot:nonroot

# Set working directory to output directory
WORKDIR /app/output

# Set PYTHONPATH to include both packages and source
ENV PYTHONPATH=/app/packages:/app/src

# Set entrypoint - use python -m
ENTRYPOINT ["python", "-m", "vibanalyz.cli"]
