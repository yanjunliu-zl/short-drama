# 构建阶段
FROM golang:1.21-alpine AS builder

RUN apk add --no-cache git ca-certificates tzdata

WORKDIR /app

# 代理设置（ARG 从 docker-compose build args 传入）
ARG https_proxy
ARG http_proxy
ARG all_proxy
ENV https_proxy=$https_proxy \
    http_proxy=$http_proxy \
    all_proxy=$all_proxy \
    GOPROXY=https://goproxy.cn,https://proxy.golang.org,direct \
    GOSUMDB=off \
    GONOSUMCHECK=* \
    GONOSUMDB=* \
    GOFLAGS=-mod=mod \
    CGO_ENABLED=0 \
    GOOS=linux

# 复制 go 模块文件并下载依赖
COPY go.mod go.sum ./
RUN go mod download

# 复制源代码并构建
COPY . .
RUN go build -a -installsuffix cgo -o final-cut-service ./cmd

# 运行阶段
FROM alpine:latest

RUN apk --no-cache add ca-certificates tzdata ffmpeg

RUN addgroup -g 1001 -S appuser && adduser -u 1001 -S appuser -G appuser
RUN mkdir -p /tmp/final-cut-workdir && chown appuser:appuser /tmp/final-cut-workdir

WORKDIR /app

COPY --from=builder /app/final-cut-service .
COPY --from=builder /app/etc/final-cut.yaml ./etc/final-cut.yaml
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo

RUN chown -R appuser:appuser /app

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8085/health || exit 1

EXPOSE 8085
ENTRYPOINT ["./final-cut-service", "-f", "etc/final-cut.yaml"]
