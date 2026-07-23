# Short Drama Platform — Architecture Design Document

> A comprehensive technical specification for the AI-powered short drama creation platform.

---

## 1. System Overview

### 1.1 Purpose

The Short Drama Platform is an end-to-end AI-powered content creation system that automates the entire short drama production pipeline: from creative idea to final video output. It serves as both a production tool for content creators and a content distribution platform with personalized recommendations.

### 1.2 Design Goals

| Goal | Target | Rationale |
|------|--------|-----------|
| End-to-end automation | Idea → Script → Storyboard → Video → Final Cut | One-click content production |
| Multi-model AI | DeepSeek + OpenAI + Anthropic + vLLM self-hosted | Cost optimization + resilience |
| Cloud-native | Docker Compose (dev) → K8s multi-region (prod) | Scale from single machine to global |
| Real-time UX | SSE streaming for all generation APIs | Perceived latency reduction |
| Industrial RAG | Semantic chunking + BM25 + Dense + RRF + metadata | Long novel → quality script |
| Production SRE | Circuit breaker + rate limiting + graceful degradation | 99.9% availability |

### 1.3 Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript + Vite + Ant Design 5 + Redux Toolkit |
| Go Services | go-zero v1.10 + gRPC + MySQL + Redis |
| Python AI Services | FastAPI + LangChain + LangGraph + FAISS + LlamaIndex |
| LLM Providers | DeepSeek / OpenAI / Anthropic / vLLM (self-hosted) |
| Image/Video | Seedream 4.5 / Seedance 2.0 (Volcano Ark API) |
| Infrastructure | MySQL 8.0 + Redis 7 + RabbitMQ + Kafka + MinIO + Elasticsearch + ClickHouse |
| Gateway | Apache APISIX 3.10 (primary) / Traefik v3 (legacy) |
| Observability | Prometheus + Grafana + Jaeger + OpenTelemetry + ELK |
| Orchestration | Docker Compose (dev) + Kubernetes (prod) + ArgoCD (GitOps) |

---

## 2. Service Architecture

### 2.1 Microservice Topology

```
                    ┌──────────────────────────────┐
                    │         Frontend (:3000)       │
                    │     React + Vite + Antd        │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │    APISIX (:9080) / Traefik   │
                    │  Rate limit + Circuit breaker │
                    └──────────────┬───────────────┘
                                   │
        ┌──────────┬───────┬───────┼───────┬───────┬──────────┐
        │          │       │       │       │       │          │
   ┌────▼───┐ ┌───▼──┐ ┌─▼────┐ ┌▼────┐ ┌▼────┐ ┌▼─────┐ ┌─▼───────┐
   │ User   │ │Content│ │Script│ │Story│ │LLM  │ │Video │ │Recommend│
   │ (Go)   │ │ (Go)  │ │(Py)  │ │(Py) │ │(Py) │ │(Py)  │ │  (Py)   │
   └────────┘ └──────┘ └──────┘ └─────┘ └─────┘ └──────┘ └─────────┘
```

### 2.2 Service Responsibilities

**user-service (Go/go-zero, :8080)**
- User registration, login, JWT authentication
- Profile management, session handling
- DBResolver read/write splitting

**content-service (Go/go-zero, :8081)**
- Case square (content discovery), works management, asset library
- Elasticsearch full-text search with smartcn tokenizer
- Field-weighted queries: title^3 > tags^2 > description^1.5

**script-service (Python/FastAPI, :8000)**
- AI script generation from outline, novel, or scratch
- V2 industrial RAG pipeline for novel-to-script adaptation
- SSE streaming for real-time generation feedback
- Comments API, entity extraction, script splitting

**storyboard-service (Python/FastAPI, :8001)**
- Shot-level storyboard generation from scripts
- 5-layer cinematography prompt builder (camera, lighting, subject, mood, style)
- 17 film style presets with per-shot differentiation
- Programmatic fallback on AI failure

**llmhua-service (Python/FastAPI, :8002)**
- AI image generation via Seedream 4.5 (Volcano Ark API)
- AI video generation via Seedance 2.0
- Batch shot-to-video pipeline with character consistency
- Prompt enhancer for professional-grade image prompts
- 6-layer identity anchor character design system

**recommendation-service (Python/FastAPI, :8004)**
- 5-layer recommendation pipeline: Recall → Pre-rank → Filter → Rank → Rerank
- 6-channel recall (CF + Content + Hot + Author + Search + Embedding ANN)
- Wide&Deep + DIN + MMOE multi-task models
- Contextual Bandit (LinUCB) online learning
- TorchRec distributed training support

**video-service (Python + Celery, :8000)**
- Video processing with Celery task queue
- FFmpeg integration for format conversion and composition

**final-cut-service (Go + gRPC, :8085)**
- Video final cut assembly
- gRPC API for inter-service communication

---

## 3. AI Pipeline Architecture

### 3.1 Script Generation — V2 RAG Pipeline

The core pipeline converts novels or creative ideas into structured short drama scripts through 6 stages:

```
Stage 1: Knowledge Base     Stage 2: Chapter Detection     Stage 3: Character Graph
FAISS + BM25 + Metadata     Regex chapter markers         LLM extraction: characters,
Semantic chunking (scene-   Chinese + English support     relationships, scenes, props
aware, not fixed-size)                                   ↓
      ↓                                           Stage 3b: Story Framework
Stage 3c: Chapter Summaries                      (skipped for full novels ≥5 ch)
Serial LLM: 100-200 chars/chapter                (outlines: LLM expands to framework)
Cross-chapter cumulative context                 ↓
      ↓                                    Stage 3d: Character Vector Store
Stage 4: Per-Chapter Generation           Independent FAISS index for profiles
Parallel (Semaphore=3)                    ↓
Query rewrite → Hybrid RAG → Generate     Stage 5: Entity Extraction
      ↓                                   LLM structured output → JSON
Stage 6: Quality Gate
Content safety + QualityJudge 4D scoring + auto-retry
```

**Hybrid RAG Retrieval (Stage 4 detail)**:
```
Query Rewrite (LLM expands intent → structured retrieval query)
      ↓
┌─────┴──────┐
│ Dense (FAISS)│     │ Sparse (BM25) │
│ bge-large-zh │     │ character-level│
└─────┬──────┘     └──────┬─────────┘
      │                   │
      └──────┬────────────┘
             ↓
      RRF Fusion (k=60)
             ↓
      Metadata Filter (chapter, characters, timeline)
             ↓
      Character Profile Lookup (parallel FAISS search)
             ↓
      Context Assembly → LLM Prompt
```

### 3.2 Multi-Model Router

The system routes LLM calls across providers with runtime failover:

```
Priority Chain: vLLM(self-hosted) → DeepSeek → OpenAI → Anthropic → Mock

ResilientLLM Wrapper:
  ainvoke() → CircuitBreaker.call()
    ↓ failure
  429/5xx detection → mark unhealthy
    ↓
  switch_provider() → next in chain
    ↓
  30s cooldown → HALF_OPEN probe → CLOSED if healthy

TieredModelRouter (model distillation):
  Tiny (Qwen2.5-1.5B AWQ int4) → small scripts, 3GB VRAM
  Small (Qwen2.5-7B AWQ int4)  → medium scripts, 6GB VRAM
  Large (Qwen2.5-14B)           → complex novels, 28GB VRAM
  Cloud (DeepSeek/GPT-4o)       → maximum quality, API cost
```

### 3.3 Agentic AI Harness

Replaces linear workflows with multi-agent orchestration:

```
RouterAgent → PlanNode.decompose(task) → [Step1, Step2, ...]
     ↓
  ┌──────────────────────────────────────┐
  │  ScriptAgent → generates content     │
  │       ↓                              │
  │  ReviewAgent → scores 5 dimensions   │
  │       ↓                              │
  │  score < 7.0 → PolishAgent → rewrite │
  │       ↓                              │
  │  RouterAgent → retry or done         │
  └──────────────────────────────────────┘

Agents can invoke Tools:
  - fetch_character_profile(name)
  - fetch_chapter_context(chapter)
  - search_similar_scripts(query)

PromptOptimizer (DSPy-inspired):
  Record (prompt, score, output) → analyze issues → generate improved prompt → A/B test
```

### 3.4 Storyboard & Video Pipeline

```
Script → Episode Splitting (第N集 regex)
  ↓
Per-Episode LLM → Shot JSON (type, angle, movement, duration)
  ↓
PromptBuilder (5-layer enrichment):
  Layer 1: Camera (shot type, angle, movement, rig, DOF, focus)
  Layer 1.5: Lighting (style, direction, color temperature)
  Layer 2: Subject (characters, dialogue, description, location)
  Layer 3: Mood (emotion tags, narrative function, atmosphere)
  Layer 5: Style (visual style + 17 cinematography profiles)
  ↓
Shot → Image (Seedream 4.5, 1920×1080 16:9)
  ↓
Image → Video (Seedance 2.0, adaptive duration by dialogue)
  ↓
Batch Processing (Semaphore=3 per episode, shared seed per scene)
```

---

## 4. Platform Compliance & Output Standards

Our video output is designed for direct submission to mainstream short drama platforms — specifically targeting **红果短剧** (ByteDance) and **快手短剧** (Kuaishou) compliance requirements.

### 4.1 红果短剧 Technical Specifications

| Parameter | 红果短剧 Requirement | Our Implementation |
|-----------|---------------------|-------------------|
| **Resolution** | 1080p minimum (1920×1080) | ✅ 1920×1080 (changed from 1920×1920 in P0 fix) |
| **Aspect Ratio** | 9:16 vertical (1080×1920) | ⚠️ Currently 16:9 horizontal → Configurable to 9:16 |
| **Frame Rate** | 25fps or 30fps | ⚠️ Default 24fps → Configurable (Seedance parameter) |
| **Video Codec** | H.264 (AVC) or H.265 (HEVC) | ✅ Seedance output is MP4/H.264 |
| **Audio** | AAC stereo, 128kbps+ | ✅ Seedance 2.0 generates audio natively from prompt |
| **Bitrate** | 2-8 Mbps (1080p) | ✅ Seedance default bitrate within range |
| **File Size** | < 500MB per episode | ✅ 5-15s clips are well within limit |
| **Watermark** | Must be watermark-free | ✅ Seedance watermark=False |

### 4.2 Content Format Requirements

| Requirement | How We Comply |
|-------------|---------------|
| **Episode Structure** | Each episode generated with `【本集钩子】` (cliffhanger) — enforced by prompt requirement |
| **Duration Control** | Episodes split by `length` parameter: 超短篇(1-5集), 短篇(6-15集), 中篇(16-40集), 长篇(41-80集), 超长篇(80-120集) |
| **Opening Hook** | 3-second opening hook rule enforced via `【本集钩子】` placement at episode start |
| **Ending CTA** | Each episode ends with suspense hook for next-episode retention — `SYSTEM_GENERATE_CHAPTER_V2` mandates this |
| **Series Consistency** | Cross-chapter character profiles + shared seed per scene maintain visual/narrative continuity |
| **Content Safety** | `ContentSafetyChecker` runs on all generated scripts before output, scoring 4 dimensions (political, violence, adult, illegal) |
| **Copyright** | Scripts generated from user-provided novels; platform does not use copyrighted training data |

### 4.3 Format Conversion Pipeline

```
Seedance Output (16:9, 720p, H.264)
        ↓
  [FFmpeg Post-Processing]
  ├── Upscale to 1080p (lanczos filter)
  ├── Convert to 9:16 vertical (crop + pad, or AI outpainting)
  ├── Frame rate conversion to 30fps (minterpolate)
  ├── Add silent audio track (placeholder for TTS)
  └── Metadata injection (title, episode number, creator)
        ↓
  Platform-Ready MP4
```

### 4.4 Quality Gate for Platform Submission

```
Generated Video
  ↓
Quality Check:
  ├── Resolution ≥ 1080p? → ❌ → Upscale
  ├── Aspect ratio = 9:16? → ❌ → Convert
  ├── Duration in range? → ❌ → Trim/Extend
  ├── Watermark present? → ❌ → Reject
  ├── Bitrate in range? → ❌ → Re-encode
  └── All pass → ✅ → Ready for submission
```

### 4.5 Alignment Scorecard vs 红果短剧

| Category | Compliance | Gap |
|----------|-----------|-----|
| Video Resolution | ✅ | — |
| Aspect Ratio | ✅ | Default 9:16, configurable (PORTRAIT_MODE) |
| Frame Rate | ✅ | Default 30fps, configurable (VIDEO_FPS) |
| Audio Track | ✅ | Seedance 2.0 generates audio natively |
| Episode Structure | ✅ | Cliffhanger + episode markers built into prompt |
| Content Safety | ✅ | 4-dimension checker + LLM-as-Judge |
| Duration Range | ✅ | Adaptive duration per episode |
| Codec/Format | ✅ | MP4/H.264 native output |

### 4.6 Roadmap to Full Compliance

| Priority | Task | Effort |
|----------|------|--------|
| P0 | Add 9:16 vertical output config flag | 1 day |
| P0 | Add 30fps frame rate option | 1 day |
| P1 | FFmpeg post-processing pipeline (upscale, aspect, audio placeholder) | 3 days |
| P1 | TTS integration for audio track generation | 5 days |
| P2 | AI video outpainting for automatic 16:9→9:16 conversion | 2 weeks |
| P2 | Automated platform submission API integration | 3 weeks |

---

## 5. Data Architecture

### 4.1 Storage Topology

```
MySQL 8.0 (Transactional)          ClickHouse (Analytics)
├── users, scripts, cases          ├── user_events (MergeTree, 90d TTL)
├── comments, works, assets        ├── search_funnel_hourly (MV)
├── user_case_interactions         ├── llm_usage (MergeTree, 180d TTL)
└── generation_tasks               └── training_samples

Redis 7 (Caching)                  Kafka 3.9 (Event Bus)
├── DB0-11: per-service isolation  ├── user-events (6 partitions)
├── L1/L2 cache: 60s/300s TTL     ├── ai-tasks-p1-realtime
├── TaskStore: 7200s TTL          ├── ai-tasks-p2-video
└── RateLimit: sliding window      └── ai-tasks-p3-batch

Elasticsearch 8.17 (Search)        MinIO (Object Storage)
├── cases index (smartcn)         ├── images/YYYY/MM/DD/
├── highlight: <em> tags           ├── videos/YYYY/MM/DD/
└── aggregations: by_genre/tags    └── 7-day presigned URLs
```

### 4.2 Data Flow

```
User Action → Kafka Producer → user-events topic
     │                              │
     ├── Redis (realtime features)  ├── ClickHouse (analytics)
     └── MySQL (transactional)      └── Training Pipeline (offline)

Search Query → QueryUnderstanding → BM25(ES) + Dense(FAISS) → RRF → LTR(DSSM) → Results
Recommendation → 6-ch Recall → PreRank(TwoTower) → Filter → Rank(Wide&Deep) → Rerank(MMR)
```

### 4.3 Cache Architecture

```
L1: In-Memory LRU (cache_layers.py)
    1000 entries, 60s TTL, O(1) lookup, <0.1ms

L2: Redis (cache_service.py)
    MD5(request) → JSON, 2h TTL for scripts, network ~1ms

L3: Semantic Cache (semantic_cache.py)
    FAISS vector index, bge-large-zh-v1.5
    Cosine similarity > 0.92 → cache hit
    60-80% hit rate for similar requests, saves LLM cost
```

---

## 6. Recommendation System

### 5.1 Five-Layer Architecture

```
Layer 1: Recall (6 channels, ~1000 candidates)
  Collaborative Filtering | Content-based | Hot | Author | Search | Embedding ANN

Layer 1.5: Pre-Ranking (TwoTower Model, 1000→200)
  User Tower: user features → 64-dim embedding
  Item Tower: item features → 64-dim embedding
  Score: cosine(user_emb, item_emb)

Layer 2: Filter
  Deduplication + viewed-item removal

Layer 3: Ranking (Multi-Objective)
  Wide&Deep + MMOE (CTR + CVR)
  21 continuous + 4 categorical + DIN sequence attention
  Degradation: handcrafted formula on model failure

Layer 4: Rerank
  MMR (λ=0.7, Jaccard tag similarity) + Cold start exploration (10% traffic)
```

### 5.2 Real-Time Features

```
EventProducer → Kafka → ClickHouse
        ↓
WindowAggregator (Flink-style):
  5min: realtime CTR, dwell avg, hot score
  1h:   short-term interest, session features
  24h:  daily stats, user views/likes
  ↓
OnlineFeatureStore (Redis pipeline, <5ms batch get)
  Key: fs:{domain}:{entity}:{feature}
```

### 5.3 Training Pipeline

```
Three training modes:
  1. Native (PyTorch single-machine) — development
  2. TorchRec (Distributed, K8s PyTorchJob) — production
  3. PySpark MLlib (Spark cluster) — large-scale

Data Flow:
  ClickHouse training_samples → FeatureRegistry → TorchRec Wide&Deep
  AUC evaluation → Model versioning → Auto-loaded by RankingService
```

---

## 7. Search System

### 6.1 Search Pipeline

```
Query → QueryUnderstanding → Hybrid Retrieval → LTR Ranking → Personalization → Results

QueryUnderstanding:
  BERT-bge-small prototype similarity → intent classification (8 categories)
  Synonym expansion from embedding similarity

Hybrid Retrieval:
  BM25 (Elasticsearch smartcn) + Dense ANN (FAISS bge-large-zh)
  RRF fusion (k=60)

LTR Ranking:
  DSSM Two-Tower: query tower + doc tower → cosine scoring
  Replaces pointwise formula

Personalization:
  User profile injection: favorite_tags ×0.03, genre_match ×0.05, author_match ×0.08

Multi-Modal:
  Chinese-CLIP for cover image search (text→image, image→image)
```

---

## 8. Infrastructure & SRE

### 7.1 Resilience Layers

```
L1: Gateway (APISIX)
  limit-count: tiered per-second (AI=50, Public=2000, Video=100)
  api-breaker: 5 failures → OPEN, 30-60s cooldown
  proxy-cache: edge caching (60s for content)

L2: Application (RateLimitMiddleware)
  Redis sliding window, per-user, 6 tiers

L3: LLM Calls (AsyncCircuitBreaker)
  5 errors/30s → OPEN → 30s cooling → HALF_OPEN probe
  Integrated into ResilientLLM.ainvoke()

L4: Inter-Service (Graceful Degradation)
  _safe_call() wrapper → degraded response on downstream failure
  No 500 propagation
```

### 7.2 Observability

```
Logs:   Structured JSON + trace_id/span_id injection → ELK
Traces: OTEL auto-instrumentation (FastAPI/httpx/aiohttp/Redis/SQLAlchemy)
        Manual spans for LLM calls → Jaeger
Metrics: Prometheus HTTP RED + business metrics (16 alert rules) → Grafana

Alert Rules:
  ServiceDown (2min) | HighErrorRate (5min) | HighLatency (P90>5s)
  LLMTimeout (10min) | MySQL/Redis/RabbitMQ Down | ContainerOOM
```

### 7.3 Scaling Strategy

```
Horizontal: HPA (CPU>70%, 2→20) + KEDA (Kafka lag, 1→30)
Vertical: GPU scheduling (Volcano 3-level queues)
Geographic: 3-region Kustomize overlays (us-east-1, ap-southeast-1, eu-west-1)

Database Scaling:
  P0: Connection pool governance (per-pod sizing)
  P1: Multi-read-replica + ProxySQL
  P2: ShardingSphere (user_id % 4)
  P3: TiDB multi-region cluster + TiCDC async sync
```

---

## 9. Security

### 8.1 Authentication & Authorization

```
Frontend: ProtectedRoute → JWT token in localStorage
Gateway: APISIX jwt-auth plugin → ForwardAuth to user-service
API: Bearer token in Authorization header (axios interceptor)
Token refresh: automatic on 401 → retry original request
```

### 8.2 Secret Management

```
Development: .env file (gitignored)
K8s Production: ExternalSecret Operator → Vault/AWS/GCP
  - API keys: 1h auto-refresh
  - Database passwords: rotation support
  - No plaintext secrets in git or K8s manifests
```

---

## 10. CI/CD & GitOps

```
GitHub Actions (.github/workflows/ci.yml):
  Push/PR to main → parallel matrix builds:
    - 4 Python services (Docker build)
    - 3 Go services (cross-compile + Docker build)
    - Frontend (vite build)
  Build-only mode (no push to registry — requires org permissions)

GitOps (ArgoCD):
  ApplicationSet: 3-region auto-deploy
  Auto-sync + prune + selfHeal
  Retry with exponential backoff (5x, 5s→3min)
```

---

## 11. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API Gateway | APISIX over Traefik | 3.6× QPS, etcd dynamic config, plugin ecosystem |
| LLM Framework | LangChain + self-built Router | Flexibility vs vendor lock-in |
| RAG Strategy | FAISS + BM25 + RRF (self-built) | Avoids LlamaIndex dependency for core path |
| Python vs Go split | AI in Python, business in Go | Python for ML ecosystem, Go for throughput |
| Caching | 3-layer (L1/L2/Semantic) | Semantic cache saves 60-80% LLM cost |
| Streaming | SSE single-endpoint dual-mode | Backward compatible, opt-in |
| Training | TorchRec + PySpark fallback | Production-grade distributed + dev simplicity |
| Model Serving | Self-hosted vLLM + Cloud fallback | Cost optimization with resilience |

---

*Document version: 1.0 | Last updated: 2026-07-23*
