# Base image with Python and Playwright browser support
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    DB_PATH=/app/data/searches.db

# Install system dependencies & Xvfb if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements & install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser
RUN playwright install chromium

# Copy application files
COPY app/ /app/app/

# Create data directory for SQLite database persistence
RUN mkdir -p /app/data

EXPOSE 8000

# Run FastAPI server with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
