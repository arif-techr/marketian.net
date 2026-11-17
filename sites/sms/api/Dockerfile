# Marketian SMS API. The same image runs the web server (default), the Celery worker and beat;
# see ../docker-compose.yml. Python 3.12 like the WA backend (DRF and Celery support it fully).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN DEBUG=False BUILD_ONLY=1 SECRET_KEY=build-only python manage.py collectstatic --noinput \
    && useradd --create-home --uid 1000 app \
    && chmod +x docker/entrypoint.sh

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)"

ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["sh", "-c", "gunicorn product.wsgi --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-2} --access-logfile - --forwarded-allow-ips '*'"]
