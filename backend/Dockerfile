FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    APP_ENV=production DATABASE_PATH=/app/data/foodverse.db \
    FOODVERSE_SKIP_DOTENV=1 WEB_CONCURRENCY=2
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY models_weights ./models_weights
RUN useradd --create-home --uid 10001 appuser && mkdir -p /app/data && chown -R appuser /app/data
USER appuser
VOLUME ["/app/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"

# --proxy-headers: trust X-Forwarded-For from the reverse proxy so rate limiting sees real client IPs.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY} --proxy-headers --forwarded-allow-ips='*'"]
