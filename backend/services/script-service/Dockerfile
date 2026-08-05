# Multi-stage build for script-service (Python ML/AI)
# Stage 1: Build — compile C extensions (torch, faiss, sentence-transformers, etc.)
FROM python:3.11-slim AS builder

ARG APT_PROXY=
ARG PIP_PROXY=

# Use Aliyun Debian mirrors
RUN sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources

# Install build dependencies
RUN if [ -n "${APT_PROXY}" ]; then \
      apt-get update -o Acquire::http::Proxy=${APT_PROXY} -o Acquire::Retries=3 && \
      apt-get install -y -o Acquire::http::Proxy=${APT_PROXY} --no-install-recommends \
      gcc g++ libpq-dev libmariadb-dev pkg-config \
      libopenblas-dev liblapack-dev cmake ninja-build git curl ca-certificates; \
    else \
      apt-get update -o Acquire::Retries=3 && \
      apt-get install -y --no-install-recommends \
      gcc g++ libpq-dev libmariadb-dev pkg-config \
      libopenblas-dev liblapack-dev cmake ninja-build git curl ca-certificates; \
    fi && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python packages to a virtualenv (preserved across stages)
COPY requirements.txt .
RUN python -m venv /opt/venv && \
    . /opt/venv/bin/activate && \
    pip install --upgrade pip && \
    if [ -n "${PIP_PROXY}" ]; then \
      pip install --no-cache-dir --proxy ${PIP_PROXY} -r requirements.txt; \
    else \
      pip install --no-cache-dir -r requirements.txt; \
    fi

# Patch openai compatibility
COPY patch_openai.py .
RUN . /opt/venv/bin/activate && python patch_openai.py; true

# Stage 2: Runtime — only runtime libs, no compilers
FROM python:3.11-slim AS runtime

ARG APT_PROXY=

# Use Aliyun Debian mirrors
RUN sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources

# Install only runtime libraries (no gcc, cmake, -dev headers)
RUN if [ -n "${APT_PROXY}" ]; then \
      apt-get update -o Acquire::http::Proxy=${APT_PROXY} -o Acquire::Retries=3 && \
      apt-get install -y -o Acquire::http::Proxy=${APT_PROXY} --no-install-recommends \
      libpq5 libmariadb3 libopenblas0 liblapack3 curl ca-certificates; \
    else \
      apt-get update -o Acquire::Retries=3 && \
      apt-get install -y --no-install-recommends \
      libpq5 libmariadb3 libopenblas0 liblapack3 curl ca-certificates; \
    fi && rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder (contains all pip packages with compiled extensions)
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV="/opt/venv"

WORKDIR /app

# Copy application code
COPY . .
RUN chown -R appuser:appuser /app/app/ 2>/dev/null; true

# Non-root user
RUN groupadd -g 1001 appuser && \
    useradd -u 1001 -g appuser -s /bin/bash -m appuser && \
    chown -R appuser:appuser /app /opt/venv

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
