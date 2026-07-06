# Short Drama Platform

An AI-powered short drama creation platform built on microservices architecture, supporting the full workflow from idea to final cut.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Frontend (React + Vite)                      │
│                     http://localhost:3000                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Traefik (:80)  │  API Gateway + Rate Limit + JWT
                    └────────┬────────┘
                             │
    ┌────────────┬───────────┼───────────┬───────────┬────────────┐
    │            │           │           │           │            │
┌───▼───┐ ┌─────▼────┐ ┌───▼────┐ ┌───▼────┐ ┌───▼────┐ ┌─────▼──────┐
│ User  │ │ Content  │ │ Script │ │ Video  │ │ LLMHua │ │ Recommend  │
│ Svc   │ │ Svc      │ │ Svc    │ │ Svc    │ │ Svc    │ │ Svc        │
│ Go    │ │ Go       │ │ Python │ │ Python │ │ Python │ │ Python     │
│ :8080 │ │ :8081    │ │ :8000  │ │ :8000  │ │ :8002  │ │ :8004      │
└───┬───┘ └─────┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └─────┬──────┘
    │           │          │          │          │            │
    └───────────┴──────────┴──────────┴──────────┴────────────┘
                             │
    ┌────────────────────────┼────────────────────────────┐
    │                        │                            │
┌───▼───┐  ┌──────▼──┐  ┌──▼───┐  ┌──────▼──┐  ┌───────▼──────┐
│ MySQL │  │  Redis  │  │ RMQ  │  │  MinIO  │  │Elasticsearch │
│  8.0  │  │  7.x    │  │ 3.x  │  │  S3     │  │    8.17      │
└───────┘  └─────────┘  └──────┘  └─────────┘  └──────────────┘
    │                                                │
    │                          ┌─────────────────────┘
    │                          │  Data sync: sync API / Logstash
    │                          ▼
    │                    ┌──────────┐
    └────────────────────│  Consul  │  Service Discovery + Health Check
                         └──────────┘
```

### Recommendation Engine (4-layer, standalone microservice)

```
User request → /api/v1/recommendations/recommend
  ↓
[Layer 1: Recall] 5-way parallel recall (~200 candidates)
  ├─ Collaborative Filtering ─ Content-based ─ Hot Trends
  ├─ Author Following ─ Search Terms
  ↓
[Layer 2: Filter] Dedup + viewed filter
  ↓
[Layer 3: Rank] CTR prediction
  ├─ PyTorch Wide&Deep (GPU node, optional)
  └─ Weighted scoring (fallback)
  ↓
[Layer 4: Rerank] MMR diversity rerank → Top-N
```

### Elasticsearch Search

```
MySQL cases → data sync (POST /api/v1/cases/sync-es)
           → Elasticsearch (smartcn Chinese tokenizer)
           → Frontend search → /api/v1/cases/search?q=keyword
              ├─ Field weights: title^3 > tags^2 > description^1.5
              ├─ Highlight: <em>keyword</em>
              ├─ Aggregations: by_genre, by_tags
              └─ Near real-time: refresh_interval=5s
```

## Services

| Service | Language | Port | Responsibility |
| ---- | ---- | ---- | ---- |
| **user-service** | Go (go-zero) | 8080 | Authentication / profile management |
| **content-service** | Go (go-zero) | 8081 | Case gallery / works / search |
| **script-service** | Python (FastAPI) | 8000 | AI script generation / comments |
| **storyboard-service** | Python (FastAPI) | 8001 | AI storyboard generation |
| **llmhua-service** | Python (FastAPI) | 8002 | AI image / video generation |
| **video-service** | Python (FastAPI) | 8000 | Video processing + Celery |
| **final-cut-service** | Go (go-zero) | 8085 | Final cut + ffmpeg + gRPC |
| **recommendation-service** | Python (FastAPI) | 8004 | Personalized recommendation engine |
| **asset-service** | Go (go-zero) | — | Asset management |
| **payment-service** | Go (go-zero) | — | Payments |
| **overview-service** | Go (go-zero) | — | Project overview |
| **scene-extractor** | Python (FastAPI) | 8003 | Scene extraction |

### Infrastructure

| Component | Version | Port | Purpose |
| ---- | ---- | ---- | ---- |
| MySQL | 8.0 | 3307→3306 | Primary database |
| Redis | 7-alpine | 6380→6379 | Cache, isolated DBs (0-11) |
| RabbitMQ | 3-management | 5672/15672 | Message queue |
| MinIO | latest | 9000/9001 | Object storage |
| Elasticsearch | 8.17.4 | 9200 | Full-text search |
| Consul | 1.20 | 8500 | Service discovery |
| Traefik | v3.0 | 80/443 | API gateway, rate limit, JWT, circuit breaker |
| Prometheus | latest | 9090 | Metrics collection |
| Grafana | latest | 3001→3000 | Monitoring dashboards |
| Jaeger | all-in-one | 16686 | Distributed tracing |

## Project Structure

```
short-drama/
├── frontend/                       # React + Vite + TypeScript + Ant Design
│   └── src/
│       ├── pages/                  # Home, CaseDetail, Script, Storyboard, ...
│       ├── components/             # CommentSection, layout, ...
│       ├── services/               # API service layer
│       ├── store/                  # Redux + redux-persist
│       └── types/                  # TypeScript type definitions
│
├── backend/
│   ├── services/
│   │   ├── user-service/           # Go | User service
│   │   ├── content-service/        # Go | Cases + works + ES search
│   │   ├── script-service/         # Python | Script generation + DeepSeek
│   │   ├── storyboard-service/     # Python | Storyboard generation
│   │   ├── llmhua-service/         # Python | AI image/video (Seedance)
│   │   ├── video-service/          # Python+Go | Video processing + Celery
│   │   ├── final-cut-service/      # Go | Final cut + ffmpeg + gRPC
│   │   ├── recommendation-service/ # Python | Recommendation engine
│   │   ├── asset-service/          # Go | Asset management
│   │   ├── payment-service/        # Go | Payments
│   │   ├── overview-service/       # Go | Overview
│   │   ├── scene-extractor/        # Python | Scene extraction
│   │   └── shared/                 # Shared modules
│   │
│   ├── api-gateway/                # Traefik dynamic config
│   │   ├── traefik.yaml
│   │   └── dynamic/
│   │       ├── routers.yaml
│   │       └── middlewares.yaml
│   │
│   ├── proto/                      # Protobuf definitions (gRPC)
│   ├── config/                     # MySQL, ES, MinIO configs
│   └── monitoring/                 # Prometheus, Grafana, Filebeat
│
├── k8s/                            # Kubernetes manifests (Kustomize)
├── docker-compose.yml              # Main compose (16 services)
├── docker-compose.consul.yml       # Consul 3-node cluster overlay
├── docker-compose.prod.yml         # Production overlay
└── Makefile
```

## Quick Start

### Prerequisites
- Docker & Docker Compose v2
- Go 1.22+ (local development)
- Python 3.11+ (local development)
- Node.js 18+ (frontend development)

### Configure API Keys

All keys are set in a single `.env` file. **Never edit `docker-compose.yml` directly for secrets.**

```bash
# Create your config from the template
cp .env.example .env
```

Edit `.env` and fill in your API keys:

```bash
# ── Required: DeepSeek API Key (script/storyboard/recommendation) ──
# Get from: https://platform.deepseek.com/api_keys
DEEPSEEK_API_KEY=sk-your-deepseek-key

# ── Required: Seedance API Key (image/video generation) ──
# Get from: https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey
SEEDANCE_API_KEY=ark-your-seedance-key

# ── Database passwords (change for production) ──
MYSQL_ROOT_PASSWORD=your-secure-password
DB_PASSWORD=your-secure-password
```

| Key | Purpose | Get From |
|---|---|---|
| `DEEPSEEK_API_KEY` | Script gen, storyboard, entity extraction | [platform.deepseek.com](https://platform.deepseek.com/api_keys) |
| `SEEDANCE_API_KEY` | Image (Seedream), Video (Seedance) | [Volcengine Ark](https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey) |

### Start All Services

```bash
# Build all images (first time ~10-20 min, subsequent builds use cache)
docker compose build

# Start all infrastructure + application services
docker compose up -d

# Check service status
docker compose ps

# Initialize Elasticsearch (first time)
curl -X POST http://localhost:8082/api/v1/cases/sync-es
```

### Access Points

| Entry | URL |
|------|------|
| Frontend | http://localhost:3000 |
| Traefik Dashboard | http://traefik.localhost (admin/admin) |
| Consul UI | http://localhost:8500 |
| RabbitMQ Management | http://localhost:15672 (admin/admin123) |
| MinIO Console | http://localhost:9001 (minioadmin/minioadmin) |
| Jaeger Tracing | http://localhost:16686 |
| Grafana | http://localhost:3001 (admin/admin) |
| Prometheus | http://localhost:9090 |
| Elasticsearch | http://localhost:9200 |
| Kibana | http://localhost:5601 |

### API Overview

```bash
# Case gallery (SQL)
GET  /api/v1/cases?page=1&pageSize=10&tag=suspense&sortBy=views

# ES full-text search (smartcn + highlight + aggregations)
GET  /api/v1/cases/search?q=CEO&pageSize=10

# Case detail
GET  /api/v1/cases/:id

# Personalized recommendation (4-layer pipeline)
GET  /api/v1/recommendations/recommend?user_id=1&limit=6

# Comments
GET  /api/v1/comments/:case_id
POST /api/v1/comments/:case_id

# gRPC (final-cut-service)
grpcurl -plaintext localhost:19085 finalcut.v1.FinalCutService/SubmitFinalCut
```

## Development Guide

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (hot reload)
npm run dev
# Visit http://localhost:3000

# Production build
npm run build

# Preview production build
npm run preview

# Lint
npm run lint

# Type check
npm run type-check

# Format code
npm run format
```

| Command | Description |
|---|---|
| `npm run dev` | Vite dev server, port 3000, hot reload |
| `npm run build` | TypeScript compile + Vite bundle to `dist/` |
| `npm run preview` | Preview production build |
| `npm run lint` | ESLint code quality check |
| `npm run type-check` | TypeScript type check (no emit) |
| `npm run format` | Prettier code formatting |

**API proxy**: The Vite dev server proxies `/api` to `http://localhost:80` (Traefik gateway). No separate backend URL configuration needed.

**Tech stack**: React 18 + TypeScript + Vite + Ant Design 5 + Redux Toolkit + React Router 6

### Go Services

```bash
cd backend/services/<service-name>

# Build (Linux cross-compile for Docker)
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o <binary> ./cmd

# Build Docker image (prebuilt binary)
docker build -t short-drama-<service>:latest -f Dockerfile.prebuilt .

# Restart single service
docker compose up -d <service-name>

# Scale stateless services (Traefik auto load-balances)
docker compose up -d --scale script-service=3
docker compose up -d --scale llmhua-service=2
```

### Python Services

```bash
cd backend/services/<service-name>

# Install dependencies
pip install -r requirements.txt

# Run locally
uvicorn main:app --host 0.0.0.0 --port <port> --reload

# Build + deploy
docker compose build <service-name>
docker compose up -d <service-name>
```

### Proto Code Generation

```bash
docker run --rm -v "$(pwd)/backend/proto:/workspace" \
  -w /workspace bufbuild/buf generate
```

### Testing

```bash
# Go unit tests
cd backend/services/<service> && go test ./...

# Python unit tests
cd backend/services/<service> && pytest

# Integration tests (requires docker compose up)
curl -s http://localhost:3000/api/v1/cases | python -m json.tool
```

## Distributed Deployment

### Architecture

All services use **environment variables** for infrastructure addresses, enabling deployment across multiple machines.

```
Machine A (Data Layer)        Machine B (AI Services)      Machine C (Gateway + Frontend)
┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
│ MySQL (primary)  │          │ script-svc ×3   │          │ Traefik :80     │
│ MySQL (read rep) │  ←────→  │ storyboard-svc   │  ←────→  │ Frontend :3000  │
│ Redis + Sentinel │          │ llmhua-svc      │          │ Consul          │
│ RabbitMQ         │          │ recommend-svc   │          │ Grafana         │
└─────────────────┘          └─────────────────┘          └─────────────────┘
```

### Load Balancing

| Layer | Mechanism | Notes |
|---|---|---|
| **HTTP API** | Traefik round-robin + health check | Auto load-balance across instances |
| **MySQL** | DBResolver (read/write split) | Write → primary, Read → replicas |
| **Redis** | Sentinel auto-failover | Automatic master failover |
| **RabbitMQ** | Quorum Queue cluster | Message high availability |

### Option 1: Single Machine, Multiple Instances

```bash
cp .env.example .env
docker compose up -d
docker compose up -d --scale script-service=3 --scale storyboard-service=2
```

### Option 2: Multi-Machine

```bash
# ── Machine A (192.168.1.10): Databases ──
docker compose up -d mysql mysql-read redis redis-sentinel rabbitmq consul

# ── Machine B (192.168.1.11): AI Services ──
# Edit .env:
#   MYSQL_HOST=192.168.1.10
#   REDIS_HOST=192.168.1.10
#   RABBITMQ_HOST=192.168.1.10
#   CONSUL_HOST=192.168.1.10
docker compose up -d script-service storyboard-service llmhua-service recommendation-service

# ── Machine C (192.168.1.12): Gateway ──
docker compose up -d traefik

# ── Any machine: add more instances ──
docker compose up -d --scale script-service=5
```

### Option 3: Docker Swarm (multi-node orchestration)

```bash
docker swarm init
docker stack deploy -c docker-compose.yml -c docker-compose.prod.yml shortdrama
docker service ls
docker service scale shortdrama_script-service=5
```

### Environment Variables

All infrastructure addresses are configurable via `.env` file. See [.env.example](.env.example).

| Variable | Default | Description |
|---|---|---|
| `MYSQL_HOST` | mysql | MySQL primary address |
| `MYSQL_READ_HOST` | mysql-read | MySQL read replica address |
| `REDIS_HOST` | redis | Redis address |
| `REDIS_SENTINEL_NODES` | (empty) | Sentinel nodes (distributed mode) |
| `RABBITMQ_HOST` | rabbitmq | RabbitMQ address |
| `CONSUL_HOST` | consul | Consul service discovery |
| `SCRIPT_SERVICE_REPLICAS` | 1 | script-service instance count |

### Production Security Checklist

1. **Secrets**: Never hardcode API keys. Use `.env` or Docker secrets
2. **Passwords**: Change all defaults (`admin/admin123`), keep `.env` consistent with all services
3. **HTTPS**: Set real domain in `traefik.yaml`, enable Let's Encrypt
4. **Firewall**: Never expose MySQL(3306)/Redis(6379) to public internet
5. **K8s**: For large-scale production, use Kubernetes — see `k8s/deploy.sh`

## License

MIT
