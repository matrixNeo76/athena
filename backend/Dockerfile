# ── ATHENA Backend — Docker image ─────────────────────────────────────────────
# python:3.11-slim keeps the image lean; curl is needed for the health-check.
FROM python:3.11-slim

WORKDIR /app

# System dependencies (curl for health-check probe)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ ./app/

# Reports directory (bind-mounted in production)
RUN mkdir -p /app/reports

EXPOSE 8000

# Uvicorn with a single worker for hackathon simplicity
# Scale with --workers N or Gunicorn in production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
