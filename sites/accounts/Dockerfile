FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CACHE_DIR=/tmp/django-cache \
    OIDC_KEY_FILE=/app/keys/oidc.pem

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# A throwaway key lets collectstatic import the settings; the real one is
# created on first start inside the "keys" volume.
RUN DEBUG=False SECRET_KEY=build-only OIDC_KEY_FILE=/tmp/build-key.pem python manage.py collectstatic --noinput \
    && rm -f /tmp/build-key.pem \
    && useradd --create-home --uid 1000 app \
    && mkdir -p /app/keys \
    && chown -R app:app /app/keys \
    && chmod +x docker/entrypoint.sh

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen(u.Request('http://127.0.0.1:8000/o/.well-known/openid-configuration', headers={'X-Forwarded-Proto': 'https'}), timeout=4)"

ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["sh", "-c", "gunicorn accountsite.wsgi --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-2} --access-logfile - --forwarded-allow-ips '*'"]
