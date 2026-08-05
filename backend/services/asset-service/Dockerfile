# 构建阶段
FROM golang:1.21-alpine AS builder

WORKDIR /app

# 复制go.mod和go.sum
COPY go.mod go.sum ./
RUN go mod download

# 复制源代码
COPY . .

# 构建应用
RUN CGO_ENABLED=0 GOOS=linux go build -o asset-service ./cmd/asset.go

# 运行阶段
FROM alpine:latest

RUN apk --no-cache add ca-certificates

WORKDIR /root/

# 从构建阶段复制二进制文件
COPY --from=builder /app/asset-service .
COPY --from=builder /app/etc/asset.yaml ./etc/asset.yaml

# 创建非root用户
RUN adduser -D -u 1000 appuser
USER appuser

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8081/health || exit 1

# 运行应用
EXPOSE 8081
CMD ["./asset-service", "-f", "etc/asset.yaml"]