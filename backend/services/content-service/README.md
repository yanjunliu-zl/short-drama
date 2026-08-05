# Content Service

内容管理服务，提供剧本创作、案例广场、作品管理等功能的API。

## 功能特性

### 1. 场景管理
- 创建、读取、更新、删除场景
- 场景排序和筛选
- 支持场景内容、地点、时间、角色等字段

### 2. 角色管理
- 创建、读取、更新、删除角色
- 角色属性：姓名、描述、年龄、性别、角色类型
- 支持分页查询

### 3. 剧本大纲
- 获取和更新剧本大纲
- 自动统计字数

### 4. 案例广场
- 浏览优秀创作案例
- 支持按标签筛选
- 支持按浏览数、点赞数、创建时间排序
- 记录浏览、点赞、分享数据

### 5. 我的作品
- 管理个人创作项目
- 支持作品状态（草稿、进行中、已完成）
- 更新作品进度
- 导出作品

## API文档

### 场景管理
- `GET    /api/v1/scenes` - 获取场景列表
- `GET    /api/v1/scenes/:id` - 获取场景详情
- `POST   /api/v1/scenes` - 创建新场景
- `PUT    /api/v1/scenes/:id` - 更新场景
- `DELETE /api/v1/scenes/:id` - 删除场景

### 角色管理
- `GET    /api/v1/characters` - 获取角色列表
- `GET    /api/v1/characters/:id` - 获取角色详情
- `POST   /api/v1/characters` - 创建新角色
- `PUT    /api/v1/characters/:id` - 更新角色
- `DELETE /api/v1/characters/:id` - 删除角色

### 剧本大纲
- `GET    /api/v1/script-outline` - 获取剧本大纲
- `PUT    /api/v1/script-outline` - 更新剧本大纲

### 案例广场
- `GET    /api/v1/cases` - 获取案例列表
- `GET    /api/v1/cases/:id` - 获取案例详情
- `POST   /api/v1/cases` - 创建案例
- `PUT    /api/v1/cases/:id` - 更新案例
- `DELETE /api/v1/cases/:id` - 删除案例
- `POST   /api/v1/cases/:id/view` - 记录浏览
- `POST   /api/v1/cases/:id/like` - 记录点赞
- `POST   /api/v1/cases/:id/share` - 记录分享

### 我的作品
- `GET    /api/v1/works` - 获取作品列表
- `GET    /api/v1/works/:id` - 获取作品详情
- `POST   /api/v1/works` - 创建新作品
- `PUT    /api/v1/works/:id` - 更新作品信息
- `PUT    /api/v1/works/:id/progress` - 更新作品进度
- `DELETE /api/v1/works/:id` - 删除作品
- `POST   /api/v1/works/:id/export` - 导出作品

## 快速开始

### 1. 安装依赖
```bash
# 设置国内代理（如果网络连接有问题）
export GOPROXY=https://goproxy.cn,direct

# 下载依赖
go mod tidy
```

### 2. 启动服务
```bash
# 开发模式
go run cmd/content.go

# 或编译后运行
go build -o content-service ./cmd/content.go
./content-service
```

### 3. 测试API
```bash
# 健康检查
curl http://localhost:8081/health

# 获取场景列表
curl http://localhost:8081/api/v1/scenes

# 获取案例列表
curl "http://localhost:8081/api/v1/cases?page=1&page_size=10&sort_by=views&order=desc"

# 获取角色列表
curl http://localhost:8081/api/v1/characters

# 获取作品列表（需要user_id参数）
curl "http://localhost:8081/api/v1/works?userId=user123&status=进行中"
```

## 配置

配置文件：`etc/content.yaml`

主要配置项：
- 服务地址和端口：`Host: 0.0.0.0`, `Port: 8081`
- 数据库配置（预留，当前使用模拟数据）
- Redis配置（预留，当前使用模拟数据）
- 日志、监控、链路追踪等

## 模拟数据

当前版本使用模拟数据，便于前端开发和测试。模拟数据包括：

### 场景数据（3个）
1. 开场 - 相遇：咖啡馆初次相遇场景
2. 对话 - 自我介绍：两人开始交谈
3. 冲突 - 误会：朋友出现引发误会

### 角色数据（3个）
1. 李明：软件工程师，主角
2. 张薇：作家，主角
3. 王强：李明的朋友，配角

### 案例数据（6个）
1. 未来都市冒险（科幻）
2. 古风爱情传奇（古风）
3. 悬疑推理剧场（悬疑）
4. 奇幻魔法世界（奇幻）
5. 职场奋斗日记（职场）
6. 家庭温情小品（家庭）

### 作品数据（3个）
1. 夏日海滩邂逅（已完成，100%）
2. 星际移民计划（进行中，65%）
3. 侦探事务所（草稿，30%）

## 开发说明

### 技术栈
- **框架**: go-zero v1.6.0
- **架构**: 分层架构（Handler -> Logic -> Repository）
- **数据**: 当前使用内存模拟数据，易于切换为真实数据库

### 项目结构
```
content-service/
├── cmd/
│   └── content.go          # 服务入口
├── etc/
│   └── content.yaml        # 配置文件
├── internal/
│   ├── config/             # 配置结构
│   ├── handler/            # HTTP处理层
│   ├── logic/              # 业务逻辑层（预留）
│   ├── repository/         # 数据访问层（预留）
│   ├── svc/                # 服务上下文
│   └── types/              # 类型定义
└── model/                  # 数据模型（预留）
```

## 下一步计划

1. **数据库集成**：将模拟数据迁移到MySQL数据库
2. **用户认证**：集成JWT认证中间件
3. **文件上传**：支持资产文件上传
4. **权限控制**：完善权限管理系统
5. **性能优化**：添加缓存、分页优化
6. **测试覆盖**：编写单元测试和集成测试

## 注意事项

- 当前版本使用模拟数据，适合开发和测试环境
- 所有API已实现CORS支持，可直接与前端对接
- 包含健康检查端点（`/health`），便于监控
- 配置文件中的数据库和Redis配置当前被注释，实际使用时需要取消注释并配置相应服务