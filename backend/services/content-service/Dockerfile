# Multi-stage build for content-service (Go)
# Stage 1: Build
# Build context: ./backend/services
FROM golang:1.24-alpine AS builder

ARG http_proxy
ARG https_proxy
ENV http_proxy=${http_proxy} https_proxy=${https_proxy}

RUN apk add --no-cache git ca-certificates tzdata

ENV GOTOOLCHAIN=auto
ENV GOPROXY=https://goproxy.cn,https://proxy.golang.org,direct

WORKDIR /app

# Copy shared module first (needed by go.mod replace directive ../shared/golang)
COPY shared/ shared/

WORKDIR /app/content-service
COPY content-service/go.mod content-service/go.sum ./
RUN go mod download

COPY content-service/. .

ARG CGO_ENABLED=0
ARG GOOS=linux
ARG GOARCH=amd64

RUN go build -a -installsuffix cgo -ldflags="-s -w" -o /usr/local/bin/content-service ./cmd

# Stage 2: Runtime
FROM alpine:3.19

RUN apk add --no-cache ca-certificates tzdata curl && \
    addgroup -g 1001 appuser && \
    adduser -u 1001 -G appuser -s /bin/sh -D appuser

WORKDIR /app

COPY --from=builder /usr/local/bin/content-service /usr/local/bin/content-service
COPY --from=builder /app/content-service/etc /app/etc

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -sf http://localhost:8081/health || exit 1

EXPOSE 8081
ENTRYPOINT ["/usr/local/bin/content-service", "-f", "etc/content.yaml"]
