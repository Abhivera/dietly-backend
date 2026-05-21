# FastAPI + Gunicorn/Uvicorn (default CMD; docker-compose.dev.yml overrides for reload)
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home --system --uid 1000 --shell /usr/sbin/nologin calovia && \
    mkdir -p /app/uploads && \
    chown -R calovia:calovia /app

COPY --chown=calovia:calovia . .

USER calovia

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=6s --start-period=50s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "120", "--workers", "1"]
