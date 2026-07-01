FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /build

RUN python -m venv /opt/venv

ENV PATH="/opt/venv/bin:${PATH}"

COPY requirements.txt /build/requirements.txt

RUN python -m pip install \
        --no-cache-dir \
        --upgrade \
        pip setuptools wheel \
    && python -m pip install \
        --no-cache-dir \
        -r /build/requirements.txt


FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:${PATH}"
ENV PORT=8000

WORKDIR /app

RUN groupadd \
        --gid 10001 \
        docurapi \
    && useradd \
        --uid 10001 \
        --gid docurapi \
        --create-home \
        --shell /usr/sbin/nologin \
        docurapi \
    && mkdir -p \
        /app/storage \
        /app/logs \
        /app/tmp \
    && chown -R \
        docurapi:docurapi \
        /app

COPY --from=builder \
    /opt/venv \
    /opt/venv

COPY --chown=docurapi:docurapi \
    . \
    /app

USER docurapi

EXPOSE 8000

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=30s \
    --retries=3 \
    CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/plans', timeout=4)"

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
