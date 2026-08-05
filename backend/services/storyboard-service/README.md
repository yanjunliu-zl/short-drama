# 分镜服务 (Storyboard Service)

基于LangChain和DeepSeek LLM的分镜生成服务。

## 功能特性

- 使用DeepSeek LLM生成高质量分镜
- 支持JSON格式输出，易于解析
- 内置缓存机制，提升性能
- 异步任务处理
- RESTful API接口

## 快速开始

### 环境要求

- Python 3.11+
- Redis (用于缓存)
- DeepSeek API Key

### 安装依赖

```bash
cd backend/services/storyboard-service
pip install -r requirements.txt
```

### 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# DeepSeek配置
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# 服务配置
HOST=0.0.0.0
PORT=8001
LOG_LEVEL=INFO
DEBUG=False
```

### 运行服务

```bash
# 本地运行
uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# Docker运行
docker build -t storyboard-service .
docker run -p 8001:8001 --env-file .env storyboard-service
```

## API接口

### 生成分镜

```bash
POST /api/v1/storyboard/generate
Content-Type: application/json

{
  "title": "剧本标题",
  "script": "剧本内容...",
  "theme": "爱情",
  "style": "写实风格",
  "scene_count": 0,
  "user_id": "user_123"
}
```

响应：
```json
{
  "task_id": "uuid",
  "status": "processing",
  "message": "Storyboard generation started",
  "storyboard": null
}
```

### 获取分镜状态

```bash
GET /api/v1/storyboard/{task_id}/status
```

### 获取分镜详情

```bash
GET /api/v1/storyboard/{storyboard_id}
```

### 获取分镜列表

```bash
GET /api/v1/storyboard?page=1&page_size=10
```

### 健康检查

```bash
GET /health
```

## API文档

服务启动后访问：
- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

## 项目结构

```
storyboard-service/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── api.py
│   │       └── endpoints/
│   │           └── storyboard.py
│   ├── core/
│   │   ├── config.py
│   │   ├── deps.py
│   │   └── logging.py
│   ├── schemas/
│   │   ├── storyboard.py
│   │   └── __init__.py
│   ├── services/
│   │   ├── storyboard_service.py
│   │   └── cache_service.py
│   └── workers/
├── main.py
├── requirements.txt
└── Dockerfile
```

## 配置说明

### DeepSeek LLM配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| DEEPSEEK_API_KEY | - | DeepSeek API密钥 |
| DEEPSEEK_API_BASE | https://api.deepseek.com | API基础URL |
| DEEPSEEK_MODEL | deepseek-chat | 模型名称 |

### 分镜生成参数

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| STORYBOARD_MAX_TOKENS | 4000 | 最大token数 |
| STORYBOARD_TEMPERATURE | 0.7 | 温度参数 |
| STORYBOARD_TIMEOUT | 60 | 超时时间(秒) |

### 缓存配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| CACHE_SCRIPT_TTL | 7200 | 分镜缓存时间(秒) |

## 使用示例

### Python客户端

```python
import httpx
import asyncio

async def generate_storyboard():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8001/api/v1/storyboard/generate",
            json={
                "title": "咖啡馆的邂逅",
                "script": "场景：咖啡馆内...",
                "theme": "爱情",
                "style": "写实风格"
            }
        )
        task_id = response.json()["task_id"]
        print(f"任务ID: {task_id}")

asyncio.run(generate_storyboard())
```

## 开发

```bash
# 安装开发依赖
pip install -r requirements.txt

# 运行测试
pytest

# 代码检查
flake8
```

## 许可证

MIT
