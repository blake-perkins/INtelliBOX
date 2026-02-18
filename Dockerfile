# EmailTools - Production Docker Image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

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
RUN useradd -m -u 1000 emailtools && \
    chown -R emailtools:emailtools /app

USER emailtools

# Health check using the /health endpoint
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use entrypoint for migrations, CMD for the actual command
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["emailtools", "web", "--host", "0.0.0.0", "--port", "8000"]
