FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖 (包括 Pillow 和 mysql 构建依赖)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    libtiff5-dev \
    libwebp-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖 (使用国内镜像加速)
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn

# 复制应用代码
COPY app ./app
COPY main.py .

# 创建非root用户
RUN useradd -m -u 1000 appuser
RUN chown -R appuser:appuser /app
USER appuser

# 暴露端口
EXPOSE 8002

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
