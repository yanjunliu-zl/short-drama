FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download 2>/dev/null || true
COPY . .
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /server ./cmd/server.go

FROM alpine:3.19
RUN apk add --no-cache ca-certificates tzdata
COPY --from=builder /server /server
EXPOSE 8005
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD wget -qO- http://localhost:8005/health || exit 1
CMD ["/server"]
