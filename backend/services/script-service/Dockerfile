FROM python:3.10-slim

ARG APT_PROXY=
ARG PIP_PROXY=

RUN if [ -n "${APT_PROXY}" ]; then \
      apt-get update -o Acquire::http::Proxy=${APT_PROXY} -o Acquire::Retries=3 && \
      apt-get install -y -o Acquire::http::Proxy=${APT_PROXY} --fix-missing --no-install-recommends \
      gcc g++ libpq-dev libmariadb-dev pkg-config \
      libopenblas-dev liblapack-dev cmake ninja-build git \
      libpq5 curl ca-certificates && \
      apt-get install -f -y -o Acquire::http::Proxy=${APT_PROXY}; \
    else \
      apt-get update -o Acquire::Retries=3 && \
      apt-get install -y --fix-missing --no-install-recommends \
      gcc g++ libpq-dev libmariadb-dev pkg-config \
      libopenblas-dev liblapack-dev cmake ninja-build git \
      libpq5 curl ca-certificates; \
    fi && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && \
    if [ -n "${PIP_PROXY}" ]; then \
      pip install --no-cache-dir --proxy ${PIP_PROXY} -r requirements.txt; \
    else \
      pip install --no-cache-dir -r requirements.txt; \
    fi

COPY . .
RUN python3 patch_openai.py && \
    find /usr/local/lib/python3.10/site-packages/openai -name '*.pyc' -delete 2>/dev/null; \
    find /usr/local/lib/python3.10/site-packages/langsmith -name '*.pyc' -delete 2>/dev/null; \
    true

RUN groupadd -g 1001 appuser && useradd -u 1001 -g appuser -s /bin/bash -m appuser && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /usr/local/lib/python3.10/site-packages/openai 2>/dev/null; \
    true

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
