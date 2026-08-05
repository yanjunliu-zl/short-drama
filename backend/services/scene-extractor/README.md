# Scene Extractor Service

一个从剧本中自动抽取场景、角色和道具的AI服务。

## 功能特点

- **场景抽取**: 从剧本中识别场景数量、地点、时间、描述、角色和道具
- **角色抽取**: 识别剧本中的角色信息，包括姓名、描述、性格、衣着等
- **道具抽取**: 识别剧本中出现的道具及其分类和用途
- **场景图像生成**: 使用Seedance AI为每个场景生成对应的图像

## 技术栈

- **Web Framework**: FastAPI
- **LLM**: DeepSeek (通过LangChain集成)
- **Image Generation**: Seedance AI
- **Configuration**: Pydantic Settings

## 快速开始

### 1. 安装依赖

```bash
cd backend/services/scene-extractor
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```bash
# DeepSeek配置
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# Seedance配置
SEEDANCE_API_URL=https://api.seedance.ai
SEEDANCE_API_KEY=your_seedance_api_key

# 服务器配置
HOST=0.0.0.0
PORT=8003
DEBUG=true
LOG_LEVEL=INFO
```

### 3. 启动服务

```bash
uvicorn main:app --host 0.0.0.0 --port 8003 --reload
```

### 4. 访问API文档

服务启动后，访问:
- Swagger UI: http://localhost:8003/docs
- ReDoc: http://localhost:8003/redoc

## API端点

### 1. 全面抽取 (场景+角色+道具)

```
POST /api/v1/scenes/
```

**请求体**:
```json
{
  "script_content": "剧本内容...",
  "extract_type": "all",
  "style": "写实风格"
}
```

**响应**:
```json
{
  "scenes": [...],
  "characters": [...],
  "props": [...],
  "extracted_at": "2024-01-01T00:00:00"
}
```

### 2. 仅抽取场景

```
POST /api/v1/scenes/scenes
```

### 3. 仅抽取角色

```
POST /api/v1/scenes/characters
```

### 4. 仅抽取道具

```
POST /api/v1/scenes/props
```

### 5. 批量生成场景图像

```
POST /api/v1/scenes/generate-scene-images
```

## 项目结构

```
scene-extractor/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── api.py                  # 路由聚合
│   │   │   └── endpoints/
│   │   │       └── scene.py            # 场景相关端点
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py                   # 配置管理
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm_service.py              # DeepSeek LLM服务
│   │   ├── seedance_service.py         # Seedance图像生成服务
│   │   └── scene_extractor_service.py  # 主要业务逻辑
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── scene.py                    # Pydantic模型
│   └── __init__.py
├── main.py                             # FastAPI应用入口
└── requirements.txt
```

## 使用示例

### Python客户端示例

```python
import asyncio
import httpx

async def extract_scenes():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8003/api/v1/scenes/",
            json={
                "script_content": "你的剧本内容...",
                "extract_type": "all",
                "style": "写实风格"
            }
        )
        result = response.json()
        print(f"场景数: {len(result['scenes'])}")
        print(f"角色数: {len(result['characters'])}")
        print(f"道具数: {len(result['props'])}")

asyncio.run(extract_scenes())
```

## License

MIT
