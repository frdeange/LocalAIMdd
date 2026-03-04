# BMS Operations — Kubernetes Manifests

This folder contains the Kubernetes manifests for deploying the BMS
multi-agent system to a cluster with Ollama + GPU.

## Structure

```
k8s/
├── argocd/                      # ArgoCD Application definitions (App of Apps)
│   ├── bms-platform.yaml        # ROOT app — manages all children
│   ├── bms-ops.yaml             # Child: BMS API + MCP services + Speech
│   ├── bms-monitoring.yaml      # Child: Tempo + ServiceMonitors + Dashboards
│   └── bms-shared-services.yaml # Child: Ollama
├── bms-ops/                     # Workload manifests → namespace bms-ops
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── bms-api.yaml
│   ├── mcp-bms.yaml
│   ├── mcp-camera.yaml
│   ├── mcp-weather.yaml
│   ├── speech-service.yaml
│   └── ingress.yaml
├── monitoring/                  # Observability → namespace monitoring
│   ├── servicemonitors.yaml
│   └── tempo.yaml
└── shared-services/             # Shared infra → namespace shared-services
    ├── namespace.yaml
    └── ollama.yaml
```

## GitOps with ArgoCD (App of Apps)

The project uses the **App of Apps** pattern. A single root Application
(`bms-platform`) points to `k8s/argocd/`, which contains child Application
manifests. ArgoCD recursively syncs everything.

### Bootstrap (one-time)

```bash
kubectl apply -f k8s/argocd/bms-platform.yaml
```

After this, ArgoCD manages all three child Applications automatically.
Any `git push` to `main` triggers a sync.

### What you see in ArgoCD portal

| Application | Source path | Target namespace |
|---|---|---|
| `bms-platform` | `k8s/argocd/` | `argocd` |
| `bms-ops` | `k8s/bms-ops/` | `bms-ops` |
| `bms-monitoring` | `k8s/monitoring/` | `monitoring` |
| `bms-shared-services` | `k8s/shared-services/` | `shared-services` |

## Prerequisites

- Ollama running in `shared-services` namespace with `qwen2.5:7b` model
- NVIDIA GPU Operator / Device Plugin installed
- Nexus Docker registry at `docker.maf.local`
- ArgoCD installed with repo `https://gitea.maf.local/kiko/LocalAIMdd.git` registered

## Deploy manually (without ArgoCD)

```bash
kubectl apply -f k8s/shared-services/
kubectl apply -f k8s/bms-ops/
kubectl apply -f k8s/monitoring/
```
