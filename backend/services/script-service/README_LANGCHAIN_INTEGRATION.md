# LangChain和LangGraph集成文档

本文档说明在script-service中引入LangChain和LangGraph进行LLM调用的集成。

## 主要功能

1. **LangChain集成**: 封装OpenAI API调用，提供剧本生成、分析和优化功能
2. **LangGraph工作流**: 实现多步骤剧本生成流程，包括草稿生成、结构分析、优化和最终化
3. **结构化服务**: 完整的服务层架构，支持异步任务处理和状态跟踪

## 新增文件

### 核心服务
- `app/services/ai_service.py` - LangChain服务，封装OpenAI调用
- `app/services/workflow.py` - LangGraph工作流，实现多步骤剧本生成
- `app/services/script_service.py` - 剧本服务，集成AI服务和工作流

### 支持文件
- `app/schemas/script.py` - 剧本相关的Pydantic模型
- `app/core/deps.py` - 依赖注入，初始化脚本服务

### 配置和示例
- `.env.example` - 环境变量配置示例
- `example_langchain_usage.py` - 使用示例脚本

## 配置更新

### 1. 依赖更新 (`requirements.txt`)
- 添加 `langgraph==0.0.28`
- 添加 `langchain-openai==0.0.8`
- 添加 `aiosqlite==0.0.19` (用于LangGraph检查点)

### 2. 配置更新 (`app/core/config.py`)
新增LangChain相关配置:
```python
OPENAI_API_BASE: Optional[str] = os.getenv("OPENAI_API_BASE", None)
OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", 2000))
OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", 0.7))
OPENAI_TIMEOUT: int = int(os.getenv("OPENAI_TIMEOUT", 30))
LANGCHAIN_TRACING: bool = os.getenv("LANGCHAIN_TRACING", "False").lower() == "true"
LANGCHAIN_ENDPOINT: Optional[str] = os.getenv("LANGCHAIN_ENDPOINT", None)
LANGCHAIN_API_KEY: Optional[str] = os.getenv("LANGCHAIN_API_KEY", None)
LANGCHAIN_PROJECT: Optional[str] = os.getenv("LANGCHAIN_PROJECT", None)
```

### 3. 应用初始化 (`main.py`)
在应用启动时初始化剧本服务:
```python
@app.on_event("startup")
async def startup_event():
    logger.info("Starting up script generation service...")
    await initialize_script_service()  # 新增
    logger.info("Service started successfully")
```

## 工作流程

### LangGraph工作流步骤
1. **初始化**: 验证请求参数，初始化AI服务
2. **生成草稿**: 使用LangChain生成剧本初稿
3. **分析结构**: 分析剧本结构，识别改进点
4. **优化剧本**: 根据分析结果优化剧本
5. **最终化**: 生成最终版本剧本

### 条件逻辑
- 根据分析结果决定是否进行优化
- 错误处理流程，确保工作流稳定性

## API使用

### 生成剧本
```python
# 通过API端点
POST /api/v1/scripts/generate

# 请求体
{
  "title": "剧本标题",
  "theme": "爱情",
  "length": "短篇",
  "characters": ["角色1", "角色2"],
  "setting": "现代都市",
  "style": "浪漫喜剧",
  "user_id": "用户ID"
}
```

### 获取状态
```python
GET /api/v1/scripts/{task_id}/status
```

## 环境变量设置

复制`.env.example`为`.env`并配置:
```bash
# 必需
OPENAI_API_KEY=your_openai_api_key_here

# 可选
LANGCHAIN_TRACING=false
LANGCHAIN_API_KEY=your_langchain_api_key_here
```

## 运行示例

1. 安装依赖:
```bash
pip install -r requirements.txt
```

2. 设置环境变量:
```bash
cp .env.example .env
# 编辑.env文件，设置OPENAI_API_KEY
```

3. 运行示例脚本:
```bash
python example_langchain_usage.py
```

4. 启动服务:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 扩展性

### 添加新的工作流步骤
1. 在`WorkflowStep`枚举中添加新步骤
2. 在`ScriptWorkflow`类中添加对应的步骤方法
3. 更新工作流图的节点和边

### 支持其他LLM提供商
1. 在`AIService`中添加新的LLM配置
2. 更新`initialize`方法以支持不同提供商
3. 通过环境变量切换模型

### 添加监控和追踪
1. 启用LangChain追踪: `LANGCHAIN_TRACING=true`
2. 配置LangSmith项目
3. 添加自定义回调处理器

## 故障排除

### 常见问题
1. **缺少OpenAI API密钥**: 设置`OPENAI_API_KEY`环境变量
2. **导入错误**: 确保已安装所有依赖
3. **工作流卡住**: 检查网络连接和API配额

### 调试建议
1. 设置`DEBUG=true`和`LOG_LEVEL=DEBUG`
2. 启用LangChain追踪进行详细调试
3. 检查工作流检查点状态

## 性能考虑

1. **API调用优化**: 批量处理请求，减少API调用次数
2. **缓存策略**: 对常用提示和结果进行缓存
3. **异步处理**: 所有AI调用都是异步的，避免阻塞
4. **超时设置**: 合理配置超时时间，避免长时间等待