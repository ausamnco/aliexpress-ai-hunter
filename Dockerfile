# Multi-stage ultra-lightweight build
FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

# Install build dependencies & Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final minimal runtime image
FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    DB_PATH=/data/searches.db \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PATH=/root/.local/bin:$PATH

# Copy installed Python packages from builder stage
COPY --from=builder /root/.local /root/.local

# Install only the minimal required shared libraries for headless Chromium shell
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    ca-certificates \
    && python3 -m playwright install --only-shell chromium \
    && apt-get purge -y --auto-remove \
    && rm -rf /var/lib/apt/lists/* /root/.cache /tmp/* /ms-playwright/ffmpeg* /ms-playwright/firefox* /ms-playwright/webkit*

# Copy application files
COPY app/ /app/app/
RUN mkdir -p /data

EXPOSE 8000

# Start lightweight FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
