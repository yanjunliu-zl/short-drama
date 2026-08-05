# 构建阶段
FROM node:18-alpine AS builder

# 安装构建依赖
RUN apk add --no-cache git python3 make g++

# 设置工作目录
WORKDIR /app

# 复制包管理文件
COPY package.json package-lock.json ./

# 安装依赖
RUN npm ci --only=production

# 复制源代码
COPY . .

# 构建应用
RUN npm run build

# 生产阶段
FROM nginx:alpine

# 安装curl用于健康检查
RUN apk add --no-cache curl

# 复制nginx配置
COPY nginx.conf /etc/nginx/nginx.conf

# 复制构建产物 (includes favicon.ico and robots.txt if present)
COPY --from=builder /app/dist /usr/share/nginx/html

# 设置权限
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html

# 暴露端口
EXPOSE 80

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/ || exit 1

# 启动nginx
CMD ["nginx", "-g", "daemon off;"]