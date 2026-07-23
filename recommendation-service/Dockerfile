FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /server ./cmd/server.go

FROM alpine:3.19
RUN apk add --no-cache ca-certificates tzdata
COPY --from=builder /server /server
EXPOSE 8004
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD wget -qO- http://localhost:8004/health || exit 1
CMD ["/server"]
