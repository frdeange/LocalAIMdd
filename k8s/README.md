# BMS Operations — Kubernetes Manifests

This folder contains the Kubernetes manifests for deploying the BMS
multi-agent system to a cluster with Ollama + GPU.

## Structure

- `namespace.yaml` — `bms-ops` namespace
- `configmap.yaml` — Environment configuration
- `deployment.yaml` — BMS Operations pod
- `argocd-app.yaml` — ArgoCD Application (GitOps)

## Prerequisites

- Ollama running in `maflocal` namespace with `qwen2.5:7b` model
- NVIDIA GPU Operator / Device Plugin installed
- Nexus Docker registry at `docker.maf.local`
- ArgoCD installed

## Deploy manually (without ArgoCD)

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
```
