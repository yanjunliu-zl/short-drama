#!/bin/bash
# Short Drama Platform — Multi-Region Full Deployment
# Supports: us-east-1 | ap-southeast-1 | eu-west-1
# GitOps: ArgoCD auto-syncs from git, this script sets up initial infra
set -euo pipefail

REGION="${1:-us-east-1}"
CONTEXT="${2:-shortdrama-$REGION}"

echo "=== Short Drama Platform — Deploying to $REGION ==="

# ── Prerequisites ──
command -v kubectl >/dev/null 2>&1 || { echo "kubectl required"; exit 1; }

# ── Secret Management (one-time setup) ──
echo "[1/4] Setting up External Secrets..."
kubectl --context="$CONTEXT" create namespace external-secrets --dry-run=client -o yaml | kubectl apply -f -
kubectl --context="$CONTEXT" apply -f k8s/security/external-secrets.yaml 2>/dev/null || true

# ── Infrastructure ──
echo "[2/4] Deploying infrastructure..."
kubectl --context="$CONTEXT" apply -k "k8s/overlays/$REGION"

# ── ArgoCD (primary region only) ──
if [ "$REGION" = "us-east-1" ]; then
    echo "[3/4] Installing ArgoCD for GitOps..."
    kubectl --context="$CONTEXT" create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
    kubectl --context="$CONTEXT" apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
    kubectl --context="$CONTEXT" apply -f k8s/argocd/applications.yaml
fi

# ── Verification ──
echo "[4/4] Verifying deployment..."
kubectl --context="$CONTEXT" get pods -n shortdrama -o wide

echo ""
echo "=== Deployed to $REGION ==="
echo "ArgoCD: kubectl port-forward svc/argocd-server -n argocd 8080:443"
echo "Next:  ./deploy.sh ap-southeast-1 && ./deploy.sh eu-west-1"
