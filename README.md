# Short Drama Platform

AI-powered short drama creation platform — end-to-end automated production from novel to video. Enterprise-grade distributed architecture with multi-model LLM routing, industrial RAG pipeline, and cloud-native operations.

## Features

### Case Square — Discover & Search
Browse trending short dramas with full-text search powered by Elasticsearch.

![Case Square](assets/main.png)

### Script Generation — AI-Powered Creation
Three creation modes to fit any workflow:

- **From Novel**: Upload a long-form novel (200+ chapters). The V2 industrial RAG pipeline auto-detects chapters, builds a dual-index knowledge base (FAISS dense + BM25 sparse), extracts character graphs and story frameworks, then generates adapted short drama scripts chapter-by-chapter with cross-chapter consistency.
- **From Outline**: Input a brief idea or outline. AI expands it into a complete script with character profiles, episode outlines, and shot-level storyboards.
- **Free Creation**: Fill in title, theme, and style. AI creates a complete script from scratch.

All modes support SSE streaming for real-time progress feedback.

![Script Generation](assets/script.png)

### Script Editor — View & Edit
Review generated scripts by episode, edit content inline, and save changes back to the cloud. Export to Xiaoyunque, LibTV, JuriLu, or download as JSON / plain text.

![Script Editor](assets/scriptboard.png)

### Scene & Character Extraction
Auto-extract scenes, characters, and props from scripts. AI generates preview images with multi-angle views. One-click smart storyboarding preserves all shot markers from the source script.

![Scene Extraction](assets/scene.png)

### Storyboard — Shot-Level Planning
AI enriches each shot with camera angles, lighting, movement, dialogue, characters, and cinematography presets. Full shot list with timeline overview and batch video generation.

![Storyboard](assets/storyboard.png)

### AI Video Generation
Generate images and videos from storyboard shots with first-frame / last-frame controls. Character library and material library for visual consistency. Batch process entire episodes with style controls.

![Video Generation](assets/video.png)

### Final Cut — Assembly & Export
Combine generated videos into a complete short drama with transitions, audio, and final rendering.

![Final Cut](assets/final-cut.png)

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

Open http://localhost:3000. The Vite dev server proxies `/api` to the API gateway.

Database tables are auto-created on first startup (MySQL auto-runs init.sql).

## AI Creation Pipeline

The platform provides a complete AI creation pipeline, accessible from the frontend pages in order:

```
Case Square → Script Generation → Script Editor → Scene Extraction → Storyboard → Video → Final Cut
```

**Script Generation** — three modes with industrial RAG pipeline:

| Mode | Input | Key Capability |
|------|-------|---------------|
| **From Novel** | Long-form novel (200+ chapters) | V2 dual-index RAG (FAISS + BM25), chapter detection, character graph, cross-chapter consistency |
| **From Outline** | Brief idea or outline | AI expands into full script with character profiles, episode outlines, storyboard |
| **Free Creation** | Title, theme, style | AI creates complete script from scratch |

The novel-to-script pipeline uses semantic chunking (scene-aware, not fixed-size), hybrid RAG retrieval (dense + sparse + RRF fusion), and multi-model routing with circuit-breaker failover. All generation APIs support SSE streaming (`stream=true`).

## Architecture

```
Frontend (:3000) → APISIX (:9080) → Microservices
                                                     ├── user-service       (Go, Auth)
                                                     ├── content-service    (Go, Cases/Search)
                                                     ├── script-service     (Python, AI Script + RAG)
                                                     ├── storyboard-service (Python, Storyboard)
                                                     ├── asset-service      (Python, Characters/Scenes/Shots)
                                                     ├── llmhua-service     (Python, Image/Video)
                                                     ├── video-service      (Python, Video Proc)
                                                     └── final-cut-service  (Go, Final Cut)

Infrastructure:     MySQL 8.0 + Redis 7 + RabbitMQ + MinIO + Kafka + Elasticsearch + ClickHouse
AI:                 DeepSeek/OpenAI/Anthropic/vLLM multi-model routing
Observability:      Prometheus + Grafana + Jaeger + OpenTelemetry (trace-log correlation)
SRE:                Circuit breaker + graceful degradation + per-user rate limiting
```

## Deployment & Operations

See [DEPLOYMENT.md](DEPLOYMENT.md) for API reference, full deployment, development, access points, and operations guides.

## License

MIT
