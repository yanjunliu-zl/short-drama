#!/bin/bash
# Build all Short Drama Platform Docker images for local K8s deployment
# Usage: ./scripts/build-images.sh [registry_prefix]
#   ./scripts/build-images.sh              # builds as shortdrama/* (default, for local)
#   ./scripts/build-images.sh docker.io/me  # pushes to docker.io/me/*
set -euo pipefail

REGISTRY="${1:-shortdrama}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Building all service images (registry: $REGISTRY) ==="

# ── Go services (use prebuilt Dockerfile where available for faster builds) ──
echo ""
echo "[1/9] content-service (Go)"
docker build -t "$REGISTRY/content-service:latest" \
  -f "$ROOT/backend/services/content-service/Dockerfile.prebuilt" \
  "$ROOT/backend/services/content-service/"

echo "[2/9] user-service (Go)"
docker build -t "$REGISTRY/user-service:latest" \
  -f "$ROOT/backend/services/user-service/Dockerfile.prebuilt" \
  "$ROOT/backend/services/user-service/"

echo "[3/9] final-cut-service (Go)"
docker build -t "$REGISTRY/final-cut-service:latest" \
  "$ROOT/backend/services/final-cut-service/"

echo "[4/9] video-service (Go)"
docker build -t "$REGISTRY/video-service:latest" \
  "$ROOT/backend/services/video-service/"

echo "[5/9] video-worker (Go)"
docker build -t "$REGISTRY/video-worker:latest" \
  -f "$ROOT/backend/services/video-service/Dockerfile.worker" \
  "$ROOT/backend/services/video-service/"

# ── Python services ──
echo "[6/9] script-service (Python)"
docker build -t "$REGISTRY/script-service:latest" \
  "$ROOT/backend/services/script-service/"

echo "[7/9] storyboard-service (Python)"
docker build -t "$REGISTRY/storyboard-service:latest" \
  "$ROOT/backend/services/storyboard-service/"

echo "[8/9] render-service (Python)"
docker build -t "$REGISTRY/render-service:latest" \
  "$ROOT/backend/services/render-service/"

# ── Frontend ──
echo "[9/9] frontend (Node)"
docker build -t "$REGISTRY/frontend:latest" \
  "$ROOT/frontend/"

echo ""
echo "=== All images built ==="
docker images | grep "$REGISTRY/" | head -20

echo ""
echo "If using a remote registry, push with:"
echo "  docker push $REGISTRY/content-service:latest"
echo "  ... (repeat for each service)"
echo ""
echo "Otherwise, for local K8s (Docker Desktop / minikube / kind):"
echo "  kubectl apply -k k8s/"
