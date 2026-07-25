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

## API Reference

### Script Generation
```bash
# Sync generation from outline (V2 pipeline)
curl -X POST http://localhost/api/v1/scripts/generate/from-outline-sync \
  -H "Content-Type: application/json" \
  -d '{"title":"Rebirth in the City","outline":"A cultivator reborn in modern city","theme":"Fantasy","length":"Short","style":"Ancient"}'

# Novel to script
curl -X POST http://localhost/api/v1/scripts/generate/from-novel \
  -H "Content-Type: application/json" \
  -d '{"title":"Adaptation","novel_content":"...","theme":"Romance","length":"Long"}'

# Stream (SSE)
curl -X POST http://localhost/api/v1/scripts/generate/from-outline-sync \
  -d '{"stream":true, "title":"...","outline":"...","theme":"...","length":"Short"}'
```

### Storyboard
```bash
curl -X POST http://localhost/api/v1/storyboard/shots/generate \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","script":"...","episodeCount":1,"style":"Realistic"}'
```

### Image / Video
```bash
# Scene image
curl -X POST http://localhost/api/v1/llmhua/images/generate \
  -d '{"scene_description":"Ancient palace interior","storyboard_id":"sb-1","scene_number":1,"style":"Ancient"}'

# Image to video
curl -X POST http://localhost/api/v1/llmhua/videos/generate \
  -d '{"image_url":"http://...","prompt":"Slow camera push-in","duration":5.0}'

# Batch shots to video
curl -X POST http://localhost/api/v1/llmhua/shots-to-video \
  -d '{"episodes":[...],"style":"Realistic"}'
```

### Other Endpoints
```bash
GET  /api/v1/cases?page=1&pageSize=10&sortBy=views
POST /api/v1/scripts/extract-entities -d '{"script_content":"...","extract_type":"all"}'
GET  /api/v1/assets/characters?limit=50
GET  /api/v1/assets/scenes?limit=50
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
