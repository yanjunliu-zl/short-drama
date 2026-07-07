# 短剧平台 (Short Drama Platform)

AI 驱动的短剧全流程创作平台，支持从创意到成片的端到端自动化生产。

## 快速开始

### 1. 配置

```bash
cp .env.example .env
```

编辑 `.env`，填入 API Key：

```env
DEEPSEEK_API_KEY=sk-xxx          # 剧本生成/分镜 (platform.deepseek.com)
SEEDANCE_API_KEY=ark-xxx         # 图像/视频生成 (console.volcengine.com/ark)
```

### 2. 启动后端

```bash
docker compose up -d
```

首次启动会自动拉取镜像并初始化数据库。等待所有服务变为 `healthy`：

```bash
docker compose ps
```

### 3. 启动前端

```bash
cd frontend && npm install && npm run dev
```

打开 http://localhost:3000，前端通过 Traefik 网关 (:80) 代理到后端。

### 4. 初始化数据

```bash
docker exec -i shortdrama-mysql mysql -uadmin -padmin123 shortdrama < backend/config/mysql/init.sql
```

## AI 创作流程

平台提供完整的 AI 创作管线，从前端页面顺序操作即可：

```
案例广场 → 剧本生成 → 场景提取 → 分镜脚本 → 分镜视频 → 成片
```

**剧本生成** — 支持三种方式：
- 从大纲生成：输入简短创意，AI 扩展为完整剧本（含角色设定 + 分集大纲 + 分镜表）
- 从小说改编：上传小说文本，自动识别章节并逐章生成剧本
- 自由创作：填写标题/主题/风格，AI 自主创作

**流式输出**：所有生成 API 支持 `stream=true` 参数启用 SSE 实时输出。

## API 概览

### 剧本生成
```bash
# 从大纲同步生成 (V2 pipeline)
curl -X POST http://localhost/api/v1/scripts/generate/from-outline-sync \
  -H "Content-Type: application/json" \
  -d '{"title":"重生之都市修仙","outline":"修真者重生到现代都市","theme":"奇幻","length":"短篇","style":"古装风格"}'

# 小说转剧本
curl -X POST http://localhost/api/v1/scripts/generate/from-novel \
  -H "Content-Type: application/json" \
  -d '{"title":"改编剧本","novel_content":"...","theme":"爱情","length":"长篇"}'

# 流式生成 (SSE)
curl -X POST http://localhost/api/v1/scripts/generate/from-outline-sync \
  -d '{"stream":true, "title":"...","outline":"...","theme":"...","length":"短篇"}'
```

### 分镜生成
```bash
# 镜头级分镜
curl -X POST http://localhost/api/v1/storyboard/shots/generate \
  -H "Content-Type: application/json" \
  -d '{"title":"测试","script":"...","episodeCount":1,"style":"写实风格"}'
```

### 图像/视频生成
```bash
# 场景图像
curl -X POST http://localhost/api/v1/llmhua/images/generate \
  -d '{"scene_description":"古代宫殿金碧辉煌","storyboard_id":"sb-1","scene_number":1,"style":"古装风格"}'

# 图像转视频
curl -X POST http://localhost/api/v1/llmhua/videos/generate \
  -d '{"image_url":"http://...","prompt":"镜头缓慢推进","duration":5.0}'

# 批量镜头转视频
curl -X POST http://localhost/api/v1/llmhua/shots-to-video \
  -d '{"episodes":[...],"style":"写实风格"}'
```

### 其他
```bash
# 案例广场
GET  /api/v1/cases?page=1&pageSize=10&sortBy=views

# 个性化推荐
GET  /api/v1/recommendations/recommend?user_id=1&limit=6

# 场景提取
POST /api/v1/scenes/ -d '{"script_content":"...","extract_type":"all"}'

# 评论区
GET  /api/v1/comments/:case_id
POST /api/v1/comments/:case_id
```

## 架构概览

```
Frontend (:3000) → Traefik (:80) → 微服务集群
                                    ├── user-service      (Go, 认证)
                                    ├── content-service   (Go, 案例/作品/搜索)
                                    ├── script-service    (Python, AI剧本)
                                    ├── storyboard-service(Python, AI分镜)
                                    ├── llmhua-service    (Python, AI图像/视频)
                                    ├── video-service     (Python, 视频处理)
                                    ├── final-cut-service (Go, 成片)
                                    └── recommendation    (Python, 推荐)

基础设施: MySQL 8.0 + Redis 7 + RabbitMQ + MinIO + Kafka + Elasticsearch
监控追踪: Prometheus + Grafana + Jaeger + OpenTelemetry
```

## 部署

### 单机
```bash
docker compose up -d
docker compose up -d --scale script-service=3   # 水平扩展
```

### 多机
```bash
# 机器 A (数据库)
docker compose up -d mysql redis rabbitmq

# 机器 B (AI 服务，.env 指向机器 A)
docker compose up -d script-service storyboard-service llmhua-service

# 机器 C (网关)
docker compose up -d traefik
```

### Kubernetes
```bash
kubectl apply -k k8s/overlays/us-east-1
```

支持 3 区域部署 (us-east-1 / ap-southeast-1 / eu-west-1)，HPA 自动扩缩 (max 20 pods)，GPU 池化调度 (Volcano)。

## 开发

```bash
# 前端
cd frontend && npm run dev          # Vite 热更新, :3000

# Python 服务
cd backend/services/script-service
pip install -r requirements.txt
uvicorn main:app --port 8000 --reload

# Go 服务 (交叉编译)
cd backend/services/user-service
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o user-service ./cmd
docker compose up -d user-service

# 测试
go test ./...          # Go
pytest                 # Python
curl localhost/api/v1/cases | python -m json.tool   # 集成测试
```

## 访问入口

| 入口 | 地址 | 凭据 |
|------|------|------|
| 前端 | http://localhost:3000 | — |
| Traefik | http://localhost:8080 | — |
| Grafana | http://localhost:3001 | admin/admin |
| RabbitMQ | http://localhost:15672 | admin/admin123 |
| MinIO | http://localhost:9001 | minioadmin/minioadmin |
| Jaeger | http://localhost:16686 | — |

## 运维

```bash
docker compose ps                        # 状态
docker compose logs -f script-service    # 日志
docker compose restart script-service    # 重启
docker compose build script-service && docker compose up -d script-service  # 更新
docker compose down                      # 停止
docker compose down -v                   # 停止+清数据
```

## 许可证

MIT
