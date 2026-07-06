# 使用 python:3.10-slim 作为基础镜像（包含 curl 和 ca-certificates）
FROM python:3.10-slim

# 安装 Go（用于构建 Go 代码）
RUN apt-get update && apt-get install -y wget git ca-certificates tzdata && rm -rf /var/lib/apt/lists/*

# 下载并安装 Go
RUN wget -q https://go.dev/dl/go1.21.0.linux-amd64.tar.gz -O /tmp/go.tar.gz && \
    tar -C /usr/local -xzf /tmp/go.tar.gz && \
    rm /tmp/go.tar.gz

ENV PATH=/usr/local/go/bin:$PATH

# 创建用户（使用非系统用户）
RUN groupadd -g 1001 appuser && useradd -u 1001 -g appuser -s /bin/bash -m appuser

WORKDIR /app

# 复制代码
COPY . .

# 设置代理（通过环境变量）
ARG https_proxy
ARG http_proxy
ARG all_proxy
ENV https_proxy=$https_proxy
ENV http_proxy=$http_proxy
ENV all_proxy=$all_proxy

# 下载依赖并构建
RUN go mod download && CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o /usr/local/bin/user-service ./cmd

# 切换到非root用户
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost:8080/health || exit 1

EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/user-service", "-f", "etc/user.yaml"]
