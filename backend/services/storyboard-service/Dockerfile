# Multi-stage build for storyboard-service (Python)
# Stage 1: Build — compile C extensions
FROM python:3.11-slim AS builder

ARG APT_PROXY=
ARG PIP_PROXY=

RUN sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources

RUN if [ -n "${APT_PROXY}" ]; then \
      apt-get update -o Acquire::http::Proxy=${APT_PROXY} -o Acquire::Retries=3 && \
      apt-get install -y -o Acquire::http::Proxy=${APT_PROXY} --no-install-recommends \
      build-essential curl ca-certificates; \
    else \
      apt-get update -o Acquire::Retries=3 && \
      apt-get install -y --no-install-recommends \
      build-essential curl ca-certificates; \
    fi && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    . /opt/venv/bin/activate && \
    pip install --upgrade pip && \
    if [ -n "${PIP_PROXY}" ]; then \
      pip install --no-cache-dir --proxy ${PIP_PROXY} -r requirements.txt; \
    else \
      pip install --no-cache-dir -r requirements.txt; \
    fi

# Stage 2: Runtime
FROM python:3.11-slim AS runtime

ARG APT_PROXY=

RUN sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources

RUN if [ -n "${APT_PROXY}" ]; then \
      apt-get update -o Acquire::http::Proxy=${APT_PROXY} -o Acquire::Retries=3 && \
      apt-get install -y -o Acquire::http::Proxy=${APT_PROXY} --no-install-recommends \
      curl ca-certificates; \
    else \
      apt-get update -o Acquire::Retries=3 && \
      apt-get install -y --no-install-recommends \
      curl ca-certificates; \
    fi && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV="/opt/venv"

WORKDIR /app

COPY app ./app
COPY main.py .

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app /opt/venv
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8001/health || exit 1

EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
