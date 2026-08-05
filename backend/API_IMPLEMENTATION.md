# 后端API实现文档

根据前端页面功能实现的后端API。

## 1. 案例广场 (Case Square)

### API端点
```
GET    /api/v1/cases           # 获取案例列表
GET    /api/v1/cases/{id}      # 获取案例详情
POST   /api/v1/cases/{id}/view # 记录浏览
POST   /api/v1/cases/{id}/like # 点赞/取消点赞
POST   /api/v1/cases/{id}/share # 记录分享
POST   /api/v1/cases           # 创建新案例（管理员）
```

### 查询参数
```
GET /api/v1/cases
- page: 页码 (默认: 1)
- page_size: 每页数量 (默认: 10, 最大: 100)
- tag: 按标签筛选 (可选)
- sort_by: 排序字段 (views, likes, createdAt)
- order: 排序顺序 (asc, desc)
```

### 示例请求
```bash
# 获取案例列表
curl -X GET "http://localhost:8000/api/v1/cases?page=1&page_size=10&sort_by=views&order=desc"

# 获取案例详情
curl -X GET "http://localhost:8000/api/v1/cases/1"

# 记录浏览
curl -X POST "http://localhost:8000/api/v1/cases/1/view"

# 点赞
curl -X POST "http://localhost:8000/api/v1/cases/1/like"
```

## 2. 我的作品 (My Works)

### API端点
```
GET    /api/v1/works                    # 获取我的作品列表
GET    /api/v1/works/{id}               # 获取作品详情
POST   /api/v1/works                    # 创建新作品
PUT    /api/v1/works/{id}               # 更新作品信息
PUT    /api/v1/works/{id}/progress      # 更新作品进度
DELETE /api/v1/works/{id}               # 删除作品
POST   /api/v1/works/{id}/export        # 导出作品
```

### 查询参数
```
GET /api/v1/works
- user_id: 用户ID (必需)
- status: 按状态筛选 (可选: 草稿, 进行中, 已完成)
- page: 页码 (默认: 1)
- page_size: 每页数量 (默认: 10, 最大: 100)
```

### 示例请求
```bash
# 获取我的作品列表
curl -X GET "http://localhost:8000/api/v1/works?user_id=user123&status=进行中"

# 创建新作品
curl -X POST "http://localhost:8000/api/v1/works" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "新作品",
    "type": "科幻短剧",
    "description": "这是一个新的科幻作品",
    "user_id": "user123"
  }'

# 更新进度
curl -X PUT "http://localhost:8000/api/v1/works/1/progress" \
  -H "Content-Type: application/json" \
  -d '{"progress": 75}'
```

## 3. 个人资产库 (Personal Assets)

### API端点
```
GET    /api/v1/assets/personal          # 获取个人资产列表
POST   /api/v1/assets/personal          # 上传个人资产
GET    /api/v1/assets/{id}              # 获取资产详情
PUT    /api/v1/assets/{id}              # 更新资产信息
DELETE /api/v1/assets/{id}              # 删除资产
POST   /api/v1/assets/{id}/use          # 使用资产
POST   /api/v1/assets/{id}/share        # 分享资产
```

### 查询参数
```
GET /api/v1/assets/personal
- user_id: 用户ID (必需)
- asset_type: 资产类型筛选 (可选: 3D模型, 场景资源, 音频资源, 视觉特效, 文本资源, 分镜资源)
- page: 页码 (默认: 1)
- page_size: 每页数量 (默认: 10, 最大: 100)
```

### 示例请求
```bash
# 获取个人资产列表
curl -X GET "http://localhost:8000/api/v1/assets/personal?user_id=user123&asset_type=3D模型"

# 上传个人资产
curl -X POST "http://localhost:8000/api/v1/assets/personal" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "新角色模型",
    "type": "3D模型",
    "count": 5,
    "description": "新创建的角色模型"
  }'

# 使用资产
curl -X POST "http://localhost:8000/api/v1/assets/1/use"
```

## 4. 公司资产库 (Company Assets)

### API端点
```
GET    /api/v1/assets/company           # 获取公司资产列表
POST   /api/v1/assets/company           # 创建公司资产（管理员）
GET    /api/v1/assets/{id}              # 获取资产详情
POST   /api/v1/assets/{id}/use          # 使用公司资产
```

### 查询参数
```
GET /api/v1/assets/company
- user_id: 用户ID (必需，用于权限检查)
- access_level: 访问权限筛选 (可选: 全体员工, 设计团队, 市场部, 内容团队, 导演团队)
- page: 页码 (默认: 1)
- page_size: 每页数量 (默认: 10, 最大: 100)
```

### 示例请求
```bash
# 获取公司资产列表
curl -X GET "http://localhost:8000/api/v1/assets/company?user_id=user123"

# 使用公司资产
curl -X POST "http://localhost:8000/api/v1/assets/7/use"
```

## 5. 服务部署

### 启动服务
```bash
# script-service (包含案例广场和我的作品API)
cd backend/services/script-service
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# asset-service (资产管理API)
cd backend/services/asset-service
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### Docker Compose
更新docker-compose.yml以包含新服务：
```yaml
asset-service:
  build: ./backend/services/asset-service
  ports:
    - "8002:8000"
  environment:
    - DEBUG=True
  depends_on:
    - mysql
    - redis
```

### API网关配置
已更新`backend/api-gateway/dynamic/routers.yaml`：
- script-service路由现在支持`/api/v1/scripts`、`/api/v1/cases`和`/api/v1/works`
- 新增asset-service路由处理`/api/v1/assets`

## 6. 数据结构

### 案例 (Case)
```json
{
  "id": "string",
  "title": "string",
  "description": "string",
  "author": "string",
  "likes": 0,
  "views": 0,
  "tags": ["string"],
  "coverColor": "#1890ff",
  "createdAt": "2026-03-15T10:30:00Z",
  "updatedAt": "2026-03-18T14:20:00Z"
}
```

### 作品 (Work)
```json
{
  "id": "string",
  "title": "string",
  "status": "草稿|进行中|已完成",
  "progress": 0,
  "type": "string",
  "userId": "string",
  "createdDate": "2026-03-15",
  "lastModified": "2026-03-18",
  "createdAt": "2026-03-15T08:30:00Z",
  "updatedAt": "2026-03-18T14:20:00Z",
  "description": "string"
}
```

### 资产 (Asset)
```json
{
  "id": "string",
  "name": "string",
  "type": "3D模型|场景资源|音频资源|视觉特效|文本资源|分镜资源",
  "count": 0,
  "owner_id": "string",           // 个人资产
  "access_level": "string",       // 公司资产
  "last_update": "2026-03-18",
  "is_personal": true,
  "description": "string"
}
```

## 7. 下一步工作

1. **数据库集成**：将模拟数据替换为真实数据库（MySQL）
2. **用户认证**：添加JWT认证中间件
3. **文件上传**：实现资产文件上传功能
4. **权限控制**：完善公司资产的权限管理系统
5. **测试**：编写单元测试和集成测试
6. **性能优化**：添加缓存、分页优化等

## 8. 注意事项

- 当前实现使用模拟数据，便于前端开发和测试
- 所有服务使用FastAPI框架，支持自动API文档（访问`/docs`）
- 已配置CORS，支持前端跨域请求
- 包含健康检查端点（`/health`）
- 已配置API网关路由，可通过统一入口访问所有服务