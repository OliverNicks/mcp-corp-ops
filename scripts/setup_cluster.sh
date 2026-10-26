#!/usr/bin/env bash
set -e

for tool in docker k3d kubectl; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "Error: $tool is not installed or not on PATH"
        exit 1
    fi
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="$REPO_ROOT/deploy/k8s/k3d-cluster.yaml"

if k3d cluster list -o json | grep -qi '"name":"mcp-platform"'; then
    echo "Cluster 'mcp-platform' already exists, skipping creation"
else
    k3d cluster create --config "$CONFIG_FILE"
fi

kubectl config use-context k3d-mcp-platform
kubectl wait --for=condition=Ready nodes --all --timeout=120s

kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply --server-side -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=available deployment/argocd-server -n argocd --timeout=300s

echo -e "\nDone. Nodes:"
kubectl get nodes -o wide