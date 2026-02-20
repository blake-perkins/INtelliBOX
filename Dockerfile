# INtelliBOX - Production Docker Image
FROM registry1.dso.mil/ironbank/redhat/ubi/ubi9

# Set working directory
WORKDIR /app

# Install Python 3.12 and system dependencies
RUN dnf install -y \
    python3.12 \
    python3.12-pip \
    python3.12-devel \
    gcc \
    gcc-c++ \
    libpq-devel \
    && dnf clean all
# Note: curl-minimal is pre-installed in UBI 9 (used by HEALTHCHECK)

# Make python3.12 the default
RUN alternatives --set python3 /usr/bin/python3.12 || true && \
    ln -sf /usr/bin/python3.12 /usr/bin/python && \
    ln -sf /usr/bin/pip3.12 /usr/bin/pip

# Copy dependency files
COPY pyproject.toml /app/

# Copy application code (needed before install)
COPY src/ /app/src/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/

# Install Python dependencies and application
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Copy entrypoint
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# Create data directories
RUN mkdir -p /app/data/inbox /app/data/emails

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose web interface port
EXPOSE 8000

# Create non-root user for security
RUN useradd -m -u 1000 intellibox && \
    chown -R intellibox:intellibox /app

USER intellibox

# Health check using the /health endpoint
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use entrypoint for migrations, CMD for the actual command
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["intellibox", "web", "--host", "0.0.0.0", "--port", "8000"]
