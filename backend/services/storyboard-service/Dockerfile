FROM python:3.11-slim

WORKDIR /app

# Proxy for apt — ENV doesn't work for apt, must use -o flag
ARG APT_PROXY=

# 安装系统依赖
RUN apt-get update -o Acquire::http::Proxy=${APT_PROXY} && \
    apt-get install -y -o Acquire::http::Proxy=${APT_PROXY} \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir --proxy http://host.docker.internal:7897 -r requirements.txt

# 复制应用代码
COPY app ./app
COPY main.py .

# 创建非root用户
RUN useradd -m -u 1000 appuser
RUN chown -R appuser:appuser /app
USER appuser

# 暴露端口
EXPOSE 8001

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
