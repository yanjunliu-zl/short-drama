# 使用 python:3.10-slim 作为基础镜像（包含 curl 和 ca-certificates）
FROM python:3.10-slim

# 安装 Go 和其他依赖
RUN apt-get update && apt-get install -y wget git ca-certificates tzdata ffmpeg && rm -rf /var/lib/apt/lists/*

# 下载并安装 Go
RUN wget -q https://go.dev/dl/go1.25.1.linux-amd64.tar.gz -O /tmp/go.tar.gz && \
    tar -C /usr/local -xzf /tmp/go.tar.gz && \
    rm /tmp/go.tar.gz

ENV PATH=/usr/local/go/bin:$PATH

# 创建用户
RUN groupadd -g 1001 appuser && useradd -u 1001 -g appuser -s /bin/bash -m appuser

WORKDIR /app

COPY . .

ARG https_proxy
ARG http_proxy
ARG all_proxy
ENV https_proxy=$https_proxy \
    http_proxy=$http_proxy \
    all_proxy=$all_proxy \
    GOPROXY=https://goproxy.cn,https://proxy.golang.org,direct \
    GOSUMDB=off \
    GOTOOLCHAIN=auto

RUN go mod download && go build -a -installsuffix cgo -o /usr/local/bin/final-cut-service ./cmd

RUN mkdir -p /tmp/final-cut-workdir && chown appuser:appuser /tmp/final-cut-workdir

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8085/health || exit 1

EXPOSE 8085
ENTRYPOINT ["/usr/local/bin/final-cut-service", "-f", "etc/final-cut.yaml"]
