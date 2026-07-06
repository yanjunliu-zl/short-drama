# 短剧平台 (Short Drama Platform)

基于微服务架构的 AI 短剧创作平台，支持从创意到成片的完整工作流。

## 架构全景

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端 (React + Vite)                       │
│                     http://localhost:3000                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Traefik (:80)  │  API 网关 + 限流 + JWT
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
    │                          │  数据同步: sync API / Logstash
    │                          ▼
    │                    ┌──────────┐
    └────────────────────│  Consul  │  服务发现 + 健康检查
                         └──────────┘
```

### 推荐系统四层架构 (独立微服务)

```
用户请求 → /api/v1/recommendations/recommend
  ↓
【Layer 1: Recall】多路召回 (5路并行, ~200候选)
  ├─ 协同过滤 (CF) ─ 标签匹配 (Content) ─ 热门 (Hot)
  ├─ 作者关注 (Author) ─ 搜索词 (Search)
  ↓
【Layer 2: Filter】去重 + 已看过滤
  ↓
【Layer 3: Rank】CTR预估
  ├─ PyTorch Wide&Deep (GPU节点, 可选)
  └─ 加权公式 (降级)
  ↓
【Layer 4: Rerank】MMR 多样性重排 → Top-N
```

### Elasticsearch 搜索

```
MySQL cases → 数据同步 (POST /api/v1/cases/sync-es)
           → Elasticsearch (smartcn 中文分词)
           → 前端搜索框 → /api/v1/cases/search?q=关键词
              ├─ 字段权重: title^3 > tags^2 > description^1.5
              ├─ 高亮: <em>关键词</em>
              ├─ 聚合: by_genre, by_tags
              └─ 近实时: refresh_interval=5s
```

## 服务清单

| 服务 | 语言 | 端口 | 职责 | 新架构特性 |
| ---- | ---- | ---- | ---- | ---------- |
| **user-service** | Go (go-zero) | 8080 | 用户认证/资料管理 | DBResolver, Consul SD |
| **content-service** | Go (go-zero) | 8081 | 案例广场/作品/搜索 | ES搜索, DBResolver |
| **script-service** | Python (FastAPI) | 8000 | AI剧本生成/评论 | Redis TaskStore, 评论API |
| **storyboard-service** | Python (FastAPI) | 8001 | AI分镜生成 | DeepSeek, Redis缓存 |
| **llmhua-service** | Python (FastAPI) | 8002 | AI图像/视频生成 | Redis TaskStore, Seedance |
| **video-service** | Python (FastAPI) | 8000 | 视频处理 + Celery | Redis CacheService, pyamqp |
| **final-cut-service** | Go (go-zero) | 8085 | 视频成片+ffmpeg | **gRPC (:19085)**, DBResolver |
| **recommendation-service** | Python (FastAPI) | 8004 | 个性化推荐引擎 | 四层架构, PyTorch可选 |
| **asset-service** | Go (go-zero) | — | 资产管理 | K8s待部署 |
| **payment-service** | Go (go-zero) | — | 支付 | K8s待部署 |
| **overview-service** | Go (go-zero) | — | 项目概览 | K8s待部署 |
| **scene-extractor** | Python (FastAPI) | 8003 | 场景提取 | K8s待部署 |

### 基础设施

| 组件 | 版本 | 端口 | 用途 |
| ---- | ---- | ---- | ---- |
| MySQL | 8.0 | 3307→3306 | 主数据库, 26张表, 连接池调优 |
| Redis | 7-alpine | 6380→6379 | 缓存, DB分离(0-11) |
| RabbitMQ | 3-management | 5672/15672 | 消息队列, Quorum Queue |
| MinIO | latest | 9000/9001 | 对象存储, EC纠删码 |
| Elasticsearch | 8.17.4 | 9200 | 全文搜索, smartcn 中文分词 |
| Consul | 1.20 | 8500 | 服务发现, 健康检查 |
| Traefik | v3.0 | 80/443 | API网关, 限流, JWT, 断路器 |
| Prometheus | latest | 9090 | 指标采集 |
| Grafana | latest | 3001→3000 | 监控仪表板 |
| Jaeger | all-in-one | 16686 | 分布式链路追踪 |

## 项目结构

```
short-drama/
├── frontend/                       # React + Vite + TypeScript + Ant Design
│   └── src/
│       ├── pages/                  # Home, CaseDetail, Script, Storyboard, ...
│       ├── components/             # CommentSection, layout, ...
│       ├── services/               # API 服务层 (caseService, commentService, ...)
│       ├── store/                  # Redux + redux-persist
│       └── types/                  # TypeScript 类型定义
│
├── backend/
│   ├── services/
│   │   ├── user-service/           # Go | 用户服务
│   │   ├── content-service/        # Go | 案例+作品+ES搜索+推荐接口
│   │   │   └── internal/
│   │   │       ├── config/         # Consul, DBResolver 配置
│   │   │       ├── grpc/           # gRPC 双栈 server
│   │   │       ├── recommend/      # 召回+过滤+MMR重排
│   │   │       ├── search/         # ES Client (smartcn+boost+highlight)
│   │   │       └── repository/     # MySQL 读写分离
│   │   ├── script-service/         # Python | 剧本+评论+DeepSeek
│   │   ├── storyboard-service/     # Python | 分镜生成
│   │   ├── llmhua-service/        # Python | AI图像/视频 (Seedance)
│   │   ├── video-service/          # Python+Go | 视频处理+Celery
│   │   ├── final-cut-service/      # Go | 成片+ffmpeg+gRPC
│   │   ├── recommendation-service/ # Python | 推荐系统 (独立微服务)
│   │   │   └── app/
│   │   │       ├── services/
│   │   │       │   ├── recommendation_engine.py  # 召回→过滤→排序→重排
│   │   │       │   └── ranking_model.py          # Wide&Deep (PyTorch)
│   │   │       └── api/v1/endpoints/recommend.py # GET /recommendations/recommend
│   │   ├── asset-service/          # Go | 资产管理
│   │   ├── payment-service/        # Go | 支付
│   │   ├── overview-service/       # Go | 概览
│   │   ├── scene-extractor/        # Python | 场景提取
│   │   └── shared/                 # 共享模块
│   │       ├── golang/db/          # DBResolver (读写分离)
│   │       └── python/             # EventBus, ModelCache, AITaskDispatcher
│   │
│   ├── api-gateway/                # Traefik 动态配置
│   │   ├── traefik.yaml            # 静态配置 (entrypoint, TLS)
│   │   └── dynamic/
│   │       ├── routers.yaml        # 9个服务路由 + 限流/重试/断路器
│   │       └── middlewares.yaml    # 分层限流 (auth/AI/video/public)
│   │
│   ├── proto/                      # Protobuf 定义 (gRPC)
│   │   ├── common/                 # 共享类型
│   │   ├── user/v1/                # UserService
│   │   ├── script/v1/              # ScriptService
│   │   ├── video/v1/               # VideoService
│   │   ├── llmhua/v1/              # LlmhuaService
│   │   └── ...                     # content, storyboard, finalcut, payment, asset
│   │
│   ├── config/
│   │   ├── mysql/                  # 数据库初始化 + 迁移
│   │   ├── elasticsearch/          # ES 索引 mapping + 数据同步脚本
│   │   └── minio/                  # 存储生命周期策略
│   │
│   └── monitoring/
│       ├── prometheus/             # 抓取配置 + 告警规则
│       ├── grafana/dashboards/     # 系统监控 + 服务仪表板
│       └── filebeat/               # 日志采集 → ES
│
├── k8s/                            # Kubernetes manifests (Kustomize)
│   ├── base/                       # namespace, configmap, secrets
│   ├── infra/                      # mysql, redis, rabbitmq, minio, consul, kafka
│   ├── services/                   # 7个服务 Deployment + HPA + PDB
│   ├── mesh/                       # Linkerd ServiceProfile + injection
│   ├── gpu/                        # Volcano 队列 + GPU 调度
│   ├── monitoring/                 # ServiceMonitor + AlertManager
│   ├── networking/                 # NetworkPolicy
│   └── overlays/                   # 3区域部署 (us, sg, eu)
│
├── docker-compose.yml              # 主 compose (16个服务)
├── docker-compose.consul.yml       # Consul 3节点集群 overlay
├── docker-compose.prod.yml         # 生产 overlay (replicas + 资源限制)
└── Makefile                        # 构建/测试/lint/deploy
```

## 快速开始

### 前提条件

- Docker & Docker Compose v2.0+
- 8GB+ 可用内存
- （仅前端本地开发需要 Node.js 18+）

### 1. 克隆项目

```bash
git clone <your-repo-url> short-drama
cd short-drama
```

### 2. 配置 API Key

所有密钥统一在 `.env` 文件中配置，`docker compose` 会自动读取。**不要直接在 `docker-compose.yml` 中填写密钥。**

```bash
# 从模板创建配置文件
cp .env.example .env
```

编辑 `.env`，填入你的 API Key：

```bash
# ── 必填：DeepSeek API Key (剧本生成/分镜/推荐) ──
# 获取地址: https://platform.deepseek.com/api_keys
DEEPSEEK_API_KEY=sk-your-deepseek-key

# ── 必填：Seedance API Key (AI 图像/视频生成) ──
# 获取地址: https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey
SEEDANCE_API_KEY=ark-your-seedance-key

# ── 数据库密码 (生产环境务必修改) ──
MYSQL_ROOT_PASSWORD=your-secure-password
DB_PASSWORD=your-secure-password
```

**获取 API Key 的方式：**

| Key | 用途 | 获取地址 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 剧本生成、分镜、实体提取、推荐 | [platform.deepseek.com](https://platform.deepseek.com/api_keys) |
| `SEEDANCE_API_KEY` | 图像生成 (Seedream)、视频生成 (Seedance) | [火山引擎 Ark](https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey) |

`.env.example` 中包含所有可配置项的说明，可作为参考。

### 3. 构建并启动全部服务

```bash
# 构建所有镜像（首次约 10-20 分钟，后续构建使用缓存）
docker compose build

# 启动全部服务
docker compose up -d

# 查看启动状态（等所有服务 healthy）
docker compose ps

# 查看日志
docker compose logs -f
```

### 4. 数据库初始化

数据库表和索引由各服务**自动创建**（首次启动时 migration 自动执行）。如果需要手动验证：

```bash
# 查看已创建的表
docker compose exec mysql mysql -uadmin -padmin123 shortdrama -e "SHOW TABLES;"

# 确保 V2 列存在（script-service 自动迁移）
docker compose exec mysql mysql -uadmin -padmin123 shortdrama -e "SHOW COLUMNS FROM scripts;"
```

### 5. 启动前端

**方案 A — Docker（推荐）**：

```bash
# 构建并启动前端容器
docker compose build frontend 2>/dev/null || \
  docker build -t shortdrama-frontend frontend/
# 前端容器运行在 http://localhost:3000
```

**方案 B — 本地开发**：

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:3000
# Vite 代理自动将 /api 转发到 Traefik 网关 (:80)
```

### 6. 验证部署

```bash
# 健康检查
curl http://localhost:3000/
curl http://localhost:3000/api/v1/cases

# 测试剧本生成（需要有效的 DeepSeek API Key）
curl -X POST http://localhost:3000/api/v1/scripts/generate/from-outline-sync \
  -H "Content-Type: application/json" \
  -d '{"title":"测试","outline":"一个测试故事","theme":"测试","length":"短篇","user_id":"1"}'
```

### 访问入口

| 入口 | 地址 | 凭据 |
|------|------|------|
| 前端 | http://localhost:3000 | — |
| Traefik 仪表板 | http://localhost:8080 | — |
| Grafana | http://localhost:3001 | admin / admin |
| Prometheus | http://localhost:9090 | — |
| Alertmanager | http://localhost:9093 | — |
| Consul UI | http://localhost:8500 | — |
| RabbitMQ 管理 | http://localhost:15672 | admin / admin123 |
| MinIO 控制台 | http://localhost:9001 | minioadmin / minioadmin |
| Jaeger 追踪 | http://localhost:16686 | — |
| Elasticsearch | http://localhost:9200 | — |

### 常用运维命令

```bash
# 查看所有容器状态
docker compose ps

# 查看某个服务日志
docker compose logs -f script-service

# 重启单个服务
docker compose restart script-service

# 重建并更新单个服务
docker compose build script-service && docker compose up -d script-service

# 水平扩展无状态服务（Traefik 自动负载均衡）
docker compose up -d --scale script-service=3
docker compose up -d --scale llmhua-service=2

# 停止所有服务
docker compose down

# 停止并清理数据（危险！）
docker compose down -v
```

## 分布式部署

### 架构说明

所有服务通过**环境变量**配置基础设施地址，可以部署在不同机器上。

```
机器 A (数据库层)          机器 B (AI 服务层)         机器 C (网关 + 前端)
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ MySQL (主)       │       │ script-svc ×3   │       │ Traefik :80     │
│ MySQL (读副本)    │ ←──→  │ storyboard-svc   │ ←──→  │ Frontend :3000  │
│ Redis + Sentinel │       │ llmhua-svc      │       │ Consul          │
│ RabbitMQ         │       │ recommend-svc   │       │ Grafana         │
└─────────────────┘       └─────────────────┘       └─────────────────┘
```

### 负载均衡

| 层级 | 机制 | 说明 |
|---|---|---|
| **HTTP API** | Traefik 轮询 + 健康检查 | 多实例自动负载均衡，无需额外配置 |
| **MySQL** | DBResolver 读写分离 | 写走主库，读走副本 |
| **Redis** | Sentinel 自动故障转移 | 主节点宕机自动切换 |
| **RabbitMQ** | 集群 Quorum Queue | 消息高可用 |

### 方式一：单机多实例（扩展 CPU 利用率）

```bash
# 复制配置
cp .env.example .env

# 启动基础服务 + 3 个 script-service 实例
docker compose up -d
docker compose up -d --scale script-service=3 --scale storyboard-service=2
```

### 方式二：多机部署

```bash
# ── 机器 A (192.168.1.10): 数据库 + 中间件 ──
docker compose up -d mysql mysql-read redis redis-sentinel rabbitmq consul

# ── 机器 B (192.168.1.11): AI 服务 ──
# 编辑 .env, 指向机器 A:
#   MYSQL_HOST=192.168.1.10
#   REDIS_HOST=192.168.1.10
#   RABBITMQ_HOST=192.168.1.10
#   CONSUL_HOST=192.168.1.10
docker compose up -d script-service storyboard-service llmhua-service recommendation-service

# ── 机器 C (192.168.1.12): 网关 + 前端 ──
docker compose up -d traefik

# ── 任意机器: 扩展更多实例 ──
docker compose up -d --scale script-service=5
```

### 方式三：Docker Swarm（多机编排）

```bash
# 初始化 Swarm
docker swarm init

# 部署（含生产配置: 读副本 + Sentinel + 资源限制）
docker stack deploy -c docker-compose.yml -c docker-compose.prod.yml shortdrama

# 查看
docker service ls
docker service scale shortdrama_script-service=5
```

### 环境变量参考

所有基础设施地址通过 `.env` 文件或环境变量配置，详见 [.env.example](.env.example)。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `MYSQL_HOST` | mysql | MySQL 主库地址 |
| `MYSQL_READ_HOST` | mysql-read | MySQL 读副本地址 |
| `REDIS_HOST` | redis | Redis 地址 |
| `REDIS_SENTINEL_NODES` | (空) | Sentinel 节点列表（分布式模式） |
| `RABBITMQ_HOST` | rabbitmq | RabbitMQ 地址 |
| `CONSUL_HOST` | consul | Consul 服务发现地址 |
| `SCRIPT_SERVICE_REPLICAS` | 1 | script-service 实例数 |

### 生产安全清单

1. **密钥**：不要硬编码 API Key，使用 `.env` 文件或 Docker secrets
2. **数据库密码**：修改所有默认密码（`admin/admin123`），确保 `.env` 与所有服务一致
3. **HTTPS**：将 `traefik.yaml` 中 `example.com` 替换为真实域名，启用 Let's Encrypt
4. **防火墙**：MySQL(3306) / Redis(6379) 不暴露公网端口，仅内网可达
5. **K8s**：大规模生产建议使用 Kubernetes，参考 `k8s/deploy.sh`

### API 概览

```bash
# 案例广场 (SQL)
GET  /api/v1/cases?page=1&pageSize=10&tag=悬疑&sortBy=views

# ES 全文搜索 (smartcn 分词 + 高亮 + 聚合)
GET  /api/v1/cases/search?q=总裁&pageSize=10

# 案例详情
GET  /api/v1/cases/:id

# 个性化推荐 (四层流水线)
GET  /api/v1/recommendations/recommend?user_id=1&limit=6

# 评论区
GET  /api/v1/comments/:case_id
POST /api/v1/comments/:case_id

# gRPC 服务 (final-cut-service)
grpcurl -plaintext localhost:19085 finalcut.v1.FinalCutService/SubmitFinalCut
```

## 开发指南

### 前端开发

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器 (热更新)
npm run dev
# 访问 http://localhost:3000

# 生产构建
npm run build

# 预览生产构建
npm run preview

# 代码检查
npm run lint

# 类型检查
npm run type-check

# 格式化代码
npm run format
```

| 命令 | 说明 |
|---|---|
| `npm run dev` | Vite 开发服务器, 端口 3000, 热更新 |
| `npm run build` | TypeScript 编译 + Vite 打包到 `dist/` |
| `npm run preview` | 预览生产构建结果 |
| `npm run lint` | ESLint 代码规范检查 |
| `npm run type-check` | TypeScript 类型检查 (不输出文件) |
| `npm run format` | Prettier 代码格式化 |

**API 代理**: Vite 开发服务器将 `/api` 代理到 `http://localhost:80` (Traefik 网关), 无需单独配置后端地址。

**前端技术栈**: React 18 + TypeScript + Vite + Ant Design 5 + Redux Toolkit + React Router 6

### Go 服务开发

```bash
cd backend/services/<service-name>

# 本地编译 (Linux 交叉编译, 用于 Docker)
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o <binary> ./cmd

# 构建 Docker 镜像 (预编译二进制)
docker build -t short-drama-<service>:latest -f Dockerfile.prebuilt .

# 只重启该服务
docker compose up -d <service-name>
```

### Python 服务开发

```bash
cd backend/services/<service-name>

# 安装依赖
pip install -r requirements.txt

# 本地运行
uvicorn main:app --host 0.0.0.0 --port <port> --reload

# 构建 + 部署
docker compose build <service-name>
docker compose up -d <service-name>
```

### Proto 代码生成

```bash
docker run --rm -v "$(pwd)/backend/proto:/workspace" \
  -w /workspace bufbuild/buf generate
```

### 测试

```bash
# Go 单测
cd backend/services/<service> && go test ./...

# Python 单测
cd backend/services/<service> && pytest

# 集成测试 (需 docker compose up)
curl -s http://localhost:3000/api/v1/cases | python -m json.tool
```

## 许可证

MIT
