# 拓扑漫剧 (Topology Drama)

基于微服务架构的拓扑漫剧，使用Go和Python构建。

## 项目概述

这是一个集剧本生成、视频处理、用户管理于一体的拓扑漫剧平台。采用微服务架构，支持水平扩展，具备高可用性和可维护性。

## 技术栈

### 后端服务
- **Go服务**: 使用GoZero微服务框架
  - 用户服务、支付服务、订单服务、通知服务、媒体服务
- **Python服务**: 使用FastAPI框架
  - 剧本生成服务（AI Agent）
  - 视频处理服务（媒体处理）

### 数据库
- **MySQL**: 主数据库（关系型数据）
- **Redis**: 缓存、会话管理
- **MongoDB**: 文档存储（可选）

### 消息队列
- **RabbitMQ**: 任务队列、服务间异步通信
- **Kafka**: 日志收集、实时分析

### API网关
- **Traefik**: 反向代理、负载均衡、SSL终止

### 监控与日志
- **Prometheus + Grafana**: 指标监控
- **ELK Stack**: 日志收集与分析

### 容器与编排
- **Docker**: 容器化
- **Kubernetes**: 容器编排
- **Helm**: Kubernetes包管理

## 项目结构

```
short-drama-platform/
├── frontend/                 # 前端代码
├── backend/                  # 后端代码
│   ├── services/            # 微服务代码
│   │   ├── user-service/    # 用户服务（GoZero）
│   │   ├── script-service/  # 剧本生成服务（FastAPI）
│   │   ├── video-service/   # 视频处理服务（FastAPI）
│   │   ├── payment-service/ # 支付服务（GoZero）
│   │   ├── order-service/   # 订单服务（GoZero）
│   │   ├── notification-service/ # 通知服务（GoZero）
│   │   └── media-service/   # 媒体服务（GoZero）
│   ├── api-gateway/         # Traefik网关配置
│   ├── charts/              # Helm charts
│   ├── config/              # 配置文件
│   ├── data/                # 数据文件（模型、视频、模板）
│   ├── infrastructure/      # 基础设施代码
│   ├── message-queue/       # 消息队列配置
│   └── monitoring/          # 监控配置
├── docs/                    # 文档
├── docker-compose.yml       # Docker Compose配置
├── Makefile                 # 构建脚本
└── README.md                # 项目说明
```

## 快速开始

### 前提条件
- Docker & Docker Compose
- Go 1.20+
- Python 3.10+
- Make

### 开发环境启动
```bash
# 克隆项目
git clone <repository-url>
cd short-drama-platform

# 启动开发环境
make dev-up

# 访问服务
# 用户服务: http://localhost:8080
# 剧本服务: http://localhost:8000
# Traefik仪表板: http://localhost:8081
# RabbitMQ管理界面: http://localhost:15672
```

### 常用命令
```bash
# 启动开发环境
make dev-up

# 停止开发环境
make dev-down

# 查看服务日志
make logs

# 运行测试
make test

# 构建所有服务
make build

# 清理
make clean
```

## 服务说明

### 用户服务 (user-service)
- 用户注册、登录、认证
- 用户资料管理
- JWT令牌生成与验证
- 权限管理

### 剧本生成服务 (script-service)
- AI驱动的剧本创作
- 角色设定与对话生成
- 故事线管理
- 多语言支持

### 视频处理服务 (video-service)
- 视频合成与编辑
- 字幕添加
- 特效处理
- 格式转换与压缩

### 支付服务 (payment-service)
- 支付网关集成（支付宝、微信支付、Stripe）
- 订阅管理
- 交易记录

### 订单服务 (order-service)
- 订单创建与跟踪
- 使用记录
- 消费统计

### 通知服务 (notification-service)
- 邮件通知
- 短信通知
- 站内信
- 推送通知

### 媒体服务 (media-service)
- 素材库管理
- 版权管理
- 水印添加

## API文档

各服务启动后可通过以下地址访问API文档：
- Go服务: `http://localhost:{port}/swagger/`
- Python服务: `http://localhost:{port}/docs`

## 部署

### 开发环境
使用Docker Compose快速启动所有服务：
```bash
docker-compose up -d
```

### 生产环境
使用Kubernetes进行部署：
```bash
# 使用Helm部署
helm install short-drama ./backend/charts/

# 或使用kubectl
kubectl apply -f backend/infrastructure/kubernetes/
```

## 开发指南

### Go服务开发
1. 进入服务目录：`cd services/user-service`
2. 安装依赖：`go mod tidy`
3. 运行服务：`go run cmd/user.go`
4. 测试：`go test ./...`

### Python服务开发
1. 进入服务目录：`cd services/script-service`
2. 创建虚拟环境：`python -m venv venv`
3. 激活虚拟环境：`source venv/bin/activate`
4. 安装依赖：`pip install -r requirements.txt`
5. 运行服务：`uvicorn app.main:app --reload`

## 贡献指南

1. Fork本仓库
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m 'Add some feature'`
4. 推送到分支：`git push origin feature/your-feature`
5. 提交Pull Request

## 许可证

本项目采用MIT许可证。详见LICENSE文件。

## 联系方式

如有问题或建议，请通过以下方式联系：
- 提交Issue
- 发送邮件至：team@example.com

## 致谢

感谢所有为本项目做出贡献的开发者！