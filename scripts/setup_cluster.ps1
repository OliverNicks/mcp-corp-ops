$ErrorActionPreference = "Stop"

foreach ($tool in "docker", "k3d", "kubectl") {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "$tool is not installed or not on PATH"
    }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$config = Join-Path $repoRoot "deploy/k8s/k3d-cluster.yaml"

$existing = k3d cluster list -o json | ConvertFrom-Json | Where-Object { $_.name -eq "mcp-platform" }
if ($existing) {
    Write-Host "Cluster 'mcp-platform' already exists, skipping creation"
} else {
    k3d cluster create --config $config
}

kubectl config use-context k3d-mcp-platform
kubectl wait --for=condition=Ready nodes --all --timeout=120s

kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply --server-side -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=available deployment/argocd-server -n argocd --timeout=300s

Write-Host "`nDone. Nodes:"
kubectl get nodes -o wide