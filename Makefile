# 拓扑漫剧 Makefile

.PHONY: help dev-up dev-down logs build test clean

# 默认目标
help:
	@echo "拓扑漫剧开发命令"
	@echo ""
	@echo "用法:"
	@echo "  make <target>"
	@echo ""
	@echo "目标:"
	@echo "  dev-up     启动开发环境 (Docker Compose)"
	@echo "  dev-down   停止开发环境"
	@echo "  logs       查看服务日志"
	@echo "  build      构建所有服务"
	@echo "  test       运行测试"
	@echo "  clean      清理临时文件"
	@echo "  fmt        格式化代码"
	@echo "  lint       代码检查"
	@echo "  deps       安装依赖"
	@echo "  migrate    运行数据库迁移"
	@echo ""

# 开发环境
dev-up:
	@echo "启动开发环境..."
	docker-compose up -d
	@echo "开发环境已启动"
	@echo "用户服务: http://localhost:8080"
	@echo "剧本服务: http://localhost:8000"
	@echo "Traefik仪表板: http://localhost:8081"
	@echo "RabbitMQ管理: http://localhost:15672 (guest/guest)"
	@echo "MySQL: localhost:3306 (root:password)"
	@echo "Redis: localhost:6379"

dev-down:
	@echo "停止开发环境..."
	docker-compose down
	@echo "开发环境已停止"

dev-restart: dev-down dev-up

logs:
	@echo "查看服务日志..."
	docker-compose logs -f

# 构建
build:
	@echo "构建所有服务..."
	@echo "构建Go服务..."
	@for service in backend/services/*-service; do \
		if [ -f "$$service/go.mod" ]; then \
			echo "构建 $$service..."; \
			(cd $$service && go build -o bin/ ./cmd/...); \
		fi \
	done
	@echo "构建Python服务..."
	@for service in backend/services/*-service; do \
		if [ -f "$$service/requirements.txt" ]; then \
			echo "构建 $$service..."; \
			(cd $$service && docker build -t $$(basename $$service):latest .); \
		fi \
	done
	@echo "所有服务构建完成"

# 测试
test:
	@echo "运行测试..."
	@echo "运行Go测试..."
	@for service in backend/services/*-service; do \
		if [ -f "$$service/go.mod" ]; then \
			echo "测试 $$service..."; \
			(cd $$service && go test ./...); \
		fi \
	done
	@echo "运行Python测试..."
	@for service in backend/services/*-service; do \
		if [ -f "$$service/requirements.txt" ]; then \
			echo "测试 $$service..."; \
			(cd $$service && python -m pytest tests/ -v); \
		fi \
	done
	@echo "测试完成"

# 代码质量
fmt:
	@echo "格式化Go代码..."
	@for service in backend/services/*-service; do \
		if [ -f "$$service/go.mod" ]; then \
			echo "格式化 $$service..."; \
			(cd $$service && go fmt ./...); \
		fi \
	done
	@echo "格式化Python代码..."
	@for service in backend/services/*-service; do \
		if [ -f "$$service/requirements.txt" ]; then \
			echo "格式化 $$service..."; \
			(cd $$service && python -m black .); \
		fi \
	done
	@echo "代码格式化完成"

lint:
	@echo "检查Go代码..."
	@for service in backend/services/*-service; do \
		if [ -f "$$service/go.mod" ]; then \
			echo "检查 $$service..."; \
			(cd $$service && golangci-lint run); \
		fi \
	done
	@echo "检查Python代码..."
	@for service in backend/services/*-service; do \
		if [ -f "$$service/requirements.txt" ]; then \
			echo "检查 $$service..."; \
			(cd $$service && python -m flake8 .); \
		fi \
	done
	@echo "代码检查完成"

# 依赖管理
deps:
	@echo "安装Go依赖..."
	@for service in backend/services/*-service; do \
		if [ -f "$$service/go.mod" ]; then \
			echo "安装 $$service 依赖..."; \
			(cd $$service && go mod tidy); \
		fi \
	done
	@echo "安装Python依赖..."
	@for service in backend/services/*-service; do \
		if [ -f "$$service/requirements.txt" ]; then \
			echo "安装 $$service 依赖..."; \
			(cd $$service && pip install -r requirements.txt); \
		fi \
	done
	@echo "依赖安装完成"

# 数据库
migrate:
	@echo "运行数据库迁移..."
	@echo "运行Go服务迁移..."
	@for service in backend/services/*-service; do \
		if [ -f "$$service/go.mod" ] && [ -f "$$service/migrations" ]; then \
			echo "迁移 $$service..."; \
			(cd $$service && go run cmd/migrate.go); \
		fi \
	done
	@echo "运行Python服务迁移..."
	@for service in backend/services/*-service; do \
		if [ -f "$$service/requirements.txt" ] && [ -d "$$service/alembic" ]; then \
			echo "迁移 $$service..."; \
			(cd $$service && alembic upgrade head); \
		fi \
	done
	@echo "数据库迁移完成"

# 清理
clean:
	@echo "清理临时文件..."
	@find . -type f -name "*.log" -delete
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@find . -type d -name ".pytest_cache" -exec rm -rf {} +
	@find . -type d -name ".coverage" -exec rm -rf {} +
	@for service in backend/services/*-service; do \
		if [ -f "$$service/go.mod" ]; then \
			(cd $$service && rm -rf bin/); \
		fi \
	done
	@echo "清理完成"

# 一键初始化
init: deps build migrate
	@echo "项目初始化完成"

# 生产环境构建
prod-build:
	@echo "构建生产环境镜像..."
	docker-compose -f docker-compose.yml build --no-cache
	@echo "生产环境镜像构建完成"

# Kubernetes部署
k8s-deploy:
	@echo "部署到Kubernetes..."
	kubectl apply -f backend/infrastructure/kubernetes/
	@echo "Kubernetes部署完成"

# Helm部署
helm-deploy:
	@echo "使用Helm部署..."
	helm install short-drama ./backend/charts/
	@echo "Helm部署完成"