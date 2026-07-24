FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY main.go .
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /server main.go

FROM scratch
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /server /server
EXPOSE 8000
CMD ["/server"]
