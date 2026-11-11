# Build from repository root: docker build -f api/Dockerfile .
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 PYTHONPATH=/app/api:/app
WORKDIR /app
RUN useradd --create-home --uid 1000 appuser
COPY api/requirements.txt /app/api/requirements.txt
RUN pip install --no-cache-dir -r /app/api/requirements.txt
COPY --chown=appuser:appuser api /app/api
COPY --chown=appuser:appuser pipeline /app/pipeline
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
