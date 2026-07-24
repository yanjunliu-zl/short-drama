FROM python:3.11-slim

WORKDIR /app

ARG APT_PROXY=

# 安装系统依赖 (包括 Pillow 和 mysql 构建依赖)
RUN if [ -n "${APT_PROXY}" ]; then \
      apt-get update -o Acquire::http::Proxy=${APT_PROXY} && \
      apt-get install -y -o Acquire::http::Proxy=${APT_PROXY} --fix-missing --no-install-recommends \
      build-essential curl libjpeg-dev zlib1g-dev libfreetype-dev \
      liblcms2-dev libopenjp2-7-dev libtiff-dev libwebp-dev && \
      apt-get install -f -y -o Acquire::http::Proxy=${APT_PROXY}; \
    else \
      apt-get update && \
      apt-get install -y --fix-missing --no-install-recommends \
      build-essential curl libjpeg-dev zlib1g-dev libfreetype-dev \
      liblcms2-dev libopenjp2-7-dev libtiff-dev libwebp-dev; \
    fi && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

ARG PIP_PROXY=
RUN if [ -n "${PIP_PROXY}" ]; then \
      pip install --no-cache-dir --proxy ${PIP_PROXY} -r requirements.txt; \
    else \
      pip install --no-cache-dir -r requirements.txt; \
    fi

COPY app ./app
COPY main.py .

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8002
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
