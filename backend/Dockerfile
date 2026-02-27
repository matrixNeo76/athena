# ── ATHENA Backend — Docker image ─────────────────────────────────────────────
# python:3.11-slim keeps the image lean; curl is needed for the health-check.
FROM python:3.11-slim

# Prevent .pyc files and enable unbuffered log output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies (curl for health-check probe)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ ./app/

# Reports directory (bind-mounted in production via Docker volume)
RUN mkdir -p /app/reports

# Non-root user — run as 'athena' for container security best practices
RUN useradd -m -u 1001 athena \
    && chown -R athena:athena /app
USER athena

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=5 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Single worker for hackathon simplicity; use --workers N or Gunicorn in production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
