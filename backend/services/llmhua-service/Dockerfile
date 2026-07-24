FROM python:3.11-slim

WORKDIR /app

ARG APT_PROXY=

# 安装系统依赖 (包括 Pillow 和 mysql 构建依赖)
RUN apt-get update -o Acquire::http::Proxy=${APT_PROXY} && \
    apt-get install -y -o Acquire::http::Proxy=${APT_PROXY} --fix-missing --no-install-recommends \
    build-essential curl libjpeg-dev zlib1g-dev libfreetype-dev \
    liblcms2-dev libopenjp2-7-dev libtiff-dev libwebp-dev \
    && apt-get install -f -y -o Acquire::http::Proxy=${APT_PROXY} \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖 (通过代理访问PyPI)
RUN pip install --no-cache-dir -r requirements.txt \
    --proxy http://host.docker.internal:7897

# 复制应用代码
COPY app ./app
COPY main.py .

# 创建非root用户
RUN useradd -m -u 1000 appuser
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8002
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
