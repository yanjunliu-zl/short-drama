# Deployment & Operations Guide

## Deployment

### Single Machine
```bash
docker compose up -d                # All services
docker compose up -d --scale script-service=3   # Scale AI services
```

### Multi-Machine
```bash
# Machine A (Databases)
docker compose up -d mysql redis rabbitmq kafka clickhouse

# Machine B (AI Services, .env pointing to A)
docker compose up -d script-service storyboard-service llmhua-service

# Machine C (Gateway + Frontend)
docker compose up -d apisix
```

### Kubernetes (GitOps)
```bash
kubectl apply -k k8s/overlays/us-east-1     # US East (primary)
kubectl apply -k k8s/overlays/ap-southeast-1 # Singapore
kubectl apply -k k8s/overlays/eu-west-1     # Europe
```

3-region deployment, HPA (2→20 pods), KEDA event-driven (1→30), Volcano GPU scheduling, ArgoCD GitOps.

## Development

```bash
# Frontend
cd frontend && npm run dev              # Vite HMR, :3000

# Python service
cd backend/services/script-service
pip install -r requirements.txt
uvicorn main:app --port 8000 --reload

# Go service
cd backend/services/user-service
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o user-service ./cmd
docker compose up -d user-service

# Testing
go test ./...                          # Go
pytest                                 # Python
curl localhost:9080/api/v1/cases       # APISIX gateway
```

## Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | — |
| APISIX Gateway | http://localhost:9080 | — |
| APISIX Dashboard | http://localhost:9000 | admin/admin |
| Grafana | http://localhost:3001 | admin/admin |
| RabbitMQ | http://localhost:15672 | admin/admin123 |
| MinIO | http://localhost:9001 | minioadmin/minioadmin |
| Jaeger | http://localhost:16686 | — |
| ClickHouse | http://localhost:8123/play | — |

## Operations

```bash
docker compose ps                        # Status
docker compose logs -f script-service    # Logs
docker compose restart script-service    # Restart
docker compose build script-service && docker compose up -d script-service
docker compose down                      # Stop
docker compose down -v                   # Stop + clear data
```
