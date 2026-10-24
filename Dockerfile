FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 noair \
    && mkdir -p /data/images \
    && chown -R noair:noair /app /data
COPY --chown=noair:noair app.py asgi.py manage.py outreach.py ./
COPY --chown=noair:noair static ./static
USER noair
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn asgi:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --limit-concurrency 8 --timeout-keep-alive 5 --no-access-log --proxy-headers --forwarded-allow-ips ${FORWARDED_ALLOW_IPS:-127.0.0.1}"]
