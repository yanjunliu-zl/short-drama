# Short Drama Platform

AI-powered short drama creation platform — end-to-end automated production from idea to final cut.

## Quick Start

### 1. Configuration

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```env
DEEPSEEK_API_KEY=sk-xxx          # Script generation / Storyboard (platform.deepseek.com)
SEEDANCE_API_KEY=ark-xxx         # Image / Video generation (console.volcengine.com/ark)
```

### 2. Start Backend

```bash
docker compose up -d
```

Wait for all services to become `healthy`:

```bash
docker compose ps
```

### 3. Start Frontend

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:3000. The Vite dev server proxies `/api` to the Traefik gateway (`:80`).

### 4. Initialize Database

```bash
docker exec -i shortdrama-mysql mysql -uadmin -padmin123 shortdrama < backend/config/mysql/init.sql
```

## AI Creation Pipeline

The platform provides a complete AI creation pipeline, accessible from the frontend pages in order:

```
Case Square → Script Generation → Scene Extraction → Storyboard → Video → Final Cut
```

**Script Generation** — three modes:
- From Outline: Input a brief idea, AI expands into a full script (characters, episode outlines, storyboard)
- From Novel: Upload novel text, AI detects chapters and adapts each one
- Free Creation: Fill in title/theme/style, AI creates from scratch

**Streaming**: All generation APIs support `stream=true` for real-time SSE output.

## API Overview

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

### Other
```bash
GET  /api/v1/cases?page=1&pageSize=10&sortBy=views
GET  /api/v1/recommendations/recommend?user_id=1&limit=6
POST /api/v1/scenes/ -d '{"script_content":"...","extract_type":"all"}'
GET  /api/v1/comments/:case_id
POST /api/v1/comments/:case_id
```

## Architecture

```
Frontend (:3000) → Traefik (:80) → Microservices
                                    ├── user-service      (Go, Auth)
                                    ├── content-service   (Go, Cases/Works/Search)
                                    ├── script-service    (Python, AI Script)
                                    ├── storyboard-service(Python, AI Storyboard)
                                    ├── llmhua-service    (Python, AI Image/Video)
                                    ├── video-service     (Python, Video Processing)
                                    ├── final-cut-service (Go, Final Cut)
                                    └── recommendation    (Python, Recommendations)

Infrastructure: MySQL 8.0 + Redis 7 + RabbitMQ + MinIO + Kafka + Elasticsearch
Observability: Prometheus + Grafana + Jaeger + OpenTelemetry
```

## Deployment

### Single Machine
```bash
docker compose up -d
docker compose up -d --scale script-service=3
```

### Multi-Machine
```bash
# Machine A (Databases)
docker compose up -d mysql redis rabbitmq

# Machine B (AI Services, .env pointing to A)
docker compose up -d script-service storyboard-service llmhua-service

# Machine C (Gateway)
docker compose up -d traefik
```

### Kubernetes
```bash
kubectl apply -k k8s/overlays/us-east-1
```

Supports 3-region deployment (us-east-1 / ap-southeast-1 / eu-west-1), HPA autoscaling (max 20 pods), GPU scheduling (Volcano).

## Development

```bash
# Frontend
cd frontend && npm run dev              # Vite HMR, :3000

# Python service
cd backend/services/script-service
pip install -r requirements.txt
uvicorn main:app --port 8000 --reload

# Go service (cross-compile for Docker)
cd backend/services/user-service
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o user-service ./cmd
docker compose up -d user-service

# Testing
go test ./...              # Go
pytest                     # Python
curl localhost/api/v1/cases | python -m json.tool
```

## Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | — |
| Traefik | http://localhost:8080 | — |
| Grafana | http://localhost:3001 | admin/admin |
| RabbitMQ | http://localhost:15672 | admin/admin123 |
| MinIO | http://localhost:9001 | minioadmin/minioadmin |
| Jaeger | http://localhost:16686 | — |

## Operations

```bash
docker compose ps                        # Status
docker compose logs -f script-service    # Logs
docker compose restart script-service    # Restart
docker compose build script-service && docker compose up -d script-service
docker compose down                      # Stop
docker compose down -v                   # Stop + clear data
```

## License

MIT
