# 构建阶段
FROM python:3.10-slim AS builder

# Use Aliyun mirror for faster apt
RUN echo "deb http://mirrors.aliyun.com/debian bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libmariadb-dev \
    pkg-config \
    libopenblas-dev \
    liblapack-dev \
    cmake \
    ninja-build \
    git \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 升级pip
RUN pip install --upgrade pip
# 安装Python依赖
RUN pip install --no-cache-dir --user --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# 运行阶段
FROM python:3.10-slim

RUN echo "deb http://mirrors.aliyun.com/debian bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list

# 安装运行时依赖
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建非root用户
RUN groupadd -g 1001 appuser && useradd -u 1001 -g appuser -s /bin/bash -m appuser

# 设置工作目录
WORKDIR /app

# 从构建阶段复制Python包
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONPATH=/home/appuser/.local/lib/python3.10/site-packages

# 复制应用代码
COPY . .

# 修复 langchain_openai + openai 兼容性
# 1. 打源代码补丁
RUN python3 patch_openai.py
# 2. 删除所有 .pyc 缓存 (确保 Python 从补丁后的源码重新编译)
RUN find /home/appuser/.local/lib/python3.10/site-packages/openai -name '*.pyc' -delete && \
    find /home/appuser/.local/lib/python3.10/site-packages/langsmith -name '*.pyc' -delete 2>/dev/null || true
# 3. 修正权限以便运行时补丁也能工作
RUN chown -R appuser:appuser /home/appuser/.local/lib/python3.10/site-packages/openai && \
    chown -R appuser:appuser /home/appuser/.local/lib/python3.10/site-packages/langsmith 2>/dev/null || true

# 设置权限
RUN chown -R appuser:appuser /app
USER appuser

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]