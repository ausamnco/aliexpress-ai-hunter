# Multi-stage ultra-lightweight build
FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

# Install dependencies into user directory
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final minimal runtime image (~90MB)
FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    DB_PATH=/data/searches.db \
    PATH=/root/.local/bin:$PATH

# Copy installed Python packages from builder stage
COPY --from=builder /root/.local /root/.local

# Copy application files
COPY app/ /app/app/
RUN mkdir -p /data

EXPOSE 8000

# Start FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
