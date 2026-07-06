#!/bin/bash
# ============================================================
# Short Drama — Kubernetes 一键部署脚本
# 用法:
#   ./deploy.sh              # 部署所有服务
#   ./deploy.sh infra        # 仅部署基础设施 (MySQL/Redis/RabbitMQ/MinIO)
#   ./deploy.sh services     # 仅部署应用服务
#   ./deploy.sh scale svc N  # 手动扩缩: scale script-service 3
#   ./deploy.sh status       # 查看状态
#   ./deploy.sh destroy      # 删除所有资源
# ============================================================

set -euo pipefail
NAMESPACE="shortdrama"
KUBECTL="kubectl"

wait_for_pods() {
  local app=$1
  echo "等待 $app Pods 就绪..."
  ${KUBECTL} wait --for=condition=ready pod -l app=$app -n ${NAMESPACE} --timeout=300s 2>/dev/null || true
}

deploy_all() {
  echo "=== 部署完整 Short Drama 平台 ==="
  echo ""

  echo "[1/4] 基础设施..."
  ${KUBECTL} apply -f base/
  ${KUBECTL} apply -f infra/
  wait_for_pods mysql
  wait_for_pods redis
  wait_for_pods rabbitmq
  echo "基础设施已就绪"
  echo ""

  echo "[2/4] 应用服务..."
  ${KUBECTL} apply -f services/
  wait_for_pods user-service
  wait_for_pods content-service
  wait_for_pods script-service
  wait_for_pods storyboard-service
  wait_for_pods frontend
  echo "应用服务已就绪"
  echo ""

  echo "[3/4] Ingress 路由..."
  ${KUBECTL} apply -f ingress/
  echo "Ingress 已配置"
  echo ""

  echo "[4/4] 监控..."
  ${KUBECTL} apply -f monitoring/ 2>/dev/null || echo "Prometheus Operator 未安装，跳过 ServiceMonitor"
  echo ""

  echo "=== 部署完成 ==="
  show_status
}

deploy_infra() {
  echo "部署基础设施..."
  ${KUBECTL} apply -f base/
  ${KUBECTL} apply -f infra/
  wait_for_pods mysql
  wait_for_pods redis
  wait_for_pods rabbitmq
  echo "基础设施已就绪"
}

deploy_services() {
  echo "部署应用服务..."
  ${KUBECTL} apply -f services/
  echo "应用服务已部署"
}

scale_service() {
  local svc=$1
  local replicas=$2
  echo "缩放 $svc → $replicas 副本"
  ${KUBECTL} scale deployment $svc --replicas=$replicas -n ${NAMESPACE}
}

show_status() {
  echo ""
  echo "=== Pods ==="
  ${KUBECTL} get pods -n ${NAMESPACE} -o wide
  echo ""
  echo "=== Services ==="
  ${KUBECTL} get svc -n ${NAMESPACE}
  echo ""
  echo "=== HPA ==="
  ${KUBECTL} get hpa -n ${NAMESPACE} 2>/dev/null || echo "HPA 未配置"
}

destroy() {
  echo "确认删除所有 shortdrama 资源? [y/N]"
  read -r confirm
  if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
    ${KUBECTL} delete namespace ${NAMESPACE}
    echo "已删除"
  else
    echo "取消"
  fi
}

# 入口
case "${1:-all}" in
  all)       deploy_all ;;
  infra)     deploy_infra ;;
  services)  deploy_services ;;
  scale)     scale_service "$2" "$3" ;;
  status)    show_status ;;
  destroy)   destroy ;;
  *)
    echo "用法: $0 {all|infra|services|scale <svc> <N>|status|destroy}"
    exit 1
    ;;
esac
