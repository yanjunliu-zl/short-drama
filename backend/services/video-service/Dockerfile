# Build context: ./backend/services
FROM golang:1.21-alpine AS builder
ARG http_proxy
ARG https_proxy
ENV http_proxy=${http_proxy} https_proxy=${https_proxy}
WORKDIR /app

# Copy shared module first (needed by go.mod replace directive ../shared/golang)
COPY shared/ shared/

WORKDIR /app/video-service
COPY video-service/main.go .
COPY video-service/go.mod video-service/go.sum ./
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /server main.go

FROM scratch
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /server /server
EXPOSE 8000
CMD ["/server"]
