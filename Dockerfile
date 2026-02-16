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

# Create data directories
RUN mkdir -p /app/data/inbox /app/data/emails

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create non-root user for security
RUN useradd -m -u 1000 emailtools && \
    chown -R emailtools:emailtools /app

USER emailtools

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from emailtools.database import get_session; next(get_session()).execute('SELECT 1')" || exit 1

# Default command (can be overridden)
CMD ["emailtools", "report", "schedule"]
