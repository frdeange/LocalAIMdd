"""
Generate Travel Planner Platform Architecture Diagram
Uses the 'diagrams' library (https://diagrams.mingrammer.com/)

Architecture: Full Kubernetes cluster on Surface Book 3 (single-node)
running MAF (Microsoft Agent Framework) multi-agent travel planner
with local LLM inference via Ollama.

Components:
  - Infrastructure: MetalLB, ingress-nginx, CoreDNS LAN, cert-manager,
    Flannel CNI, NVIDIA device plugin, local-path-provisioner
  - Application: Next.js frontend, FastAPI backend, MCP server, Ollama,
    PostgreSQL, Aspire Dashboard
  - MAF Pipeline: Researcher → WeatherAnalyst → Planner (SequentialBuilder)
  - DevOps: Gitea, Nexus, ArgoCD
  - Monitoring: Grafana, Prometheus, Aspire Dashboard (OTLP)

Usage:
    pip install diagrams
    apt-get install graphviz
    python docs/generate_architecture.py

Output:
    docs/images/travel_planner_architecture.png
"""

import os
import urllib.request
from pathlib import Path

from diagrams import Diagram, Cluster, Edge
from diagrams.k8s.compute import Deploy, Pod, DaemonSet, Job
from diagrams.k8s.network import Ingress, Service
from diagrams.k8s.storage import PV, StorageClass
from diagrams.k8s.infra import Node
from diagrams.onprem.client import User
from diagrams.onprem.database import PostgreSQL
from diagrams.onprem.network import Nginx
from diagrams.onprem.monitoring import Grafana, Prometheus
from diagrams.onprem.gitops import ArgoCD
from diagrams.onprem.vcs import Gitea
from diagrams.onprem.certificates import CertManager
from diagrams.programming.framework import Fastapi, Nextjs, Dotnet, React
from diagrams.custom import Custom
from diagrams.generic.network import Firewall

# ── Paths ───────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
IMAGES_DIR = SCRIPT_DIR / "images"
ICONS_DIR = IMAGES_DIR / "icons"
OUTPUT_FILE = str(IMAGES_DIR / "travel_planner_architecture")

# ── Download custom icons ───────────────────────────────────────────
CUSTOM_ICONS = {
    "ollama": "https://ollama.com/public/ollama.png",
    "metallb": "https://raw.githubusercontent.com/metallb/metallb/main/website/static/images/logo/metallb-blue.png",
    "flannel": "https://raw.githubusercontent.com/flannel-io/flannel/master/logos/flannel-glyph-color.png",
}


def download_icons():
    """Download custom icons, falling back silently on failure."""
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    icons = {}
    for name, url in CUSTOM_ICONS.items():
        icon_path = ICONS_DIR / f"{name}.png"
        if icon_path.exists():
            icons[name] = str(icon_path)
            continue
        try:
            urllib.request.urlretrieve(url, str(icon_path))
            icons[name] = str(icon_path)
            print(f"  ✓ Downloaded {name} icon")
        except Exception:
            icons[name] = None
            print(f"  ✗ Failed to download {name} icon (will use fallback)")
    return icons


def custom_or_fallback(icons, name, label, fallback_cls=Deploy):
    """Return a Custom node if icon exists, otherwise a fallback node."""
    if icons.get(name):
        return Custom(label, icons[name])
    return fallback_cls(label)


# ── Graph styling ───────────────────────────────────────────────────
GRAPH_ATTR = {
    "bgcolor": "#0f172a",       # slate-900
    "fontcolor": "#e2e8f0",     # slate-200
    "fontsize": "16",
    "fontname": "DejaVu Sans",
    "pad": "1.0",
    "splines": "spline",
    "nodesep": "0.7",
    "ranksep": "1.2",
    "compound": "true",
    "labeljust": "l",
}

NODE_ATTR = {
    "fontcolor": "#e2e8f0",
    "fontsize": "10",
    "fontname": "DejaVu Sans",
}

# Cluster color palette
CL_INFRA = {"bgcolor": "#0c1929", "fontcolor": "#67e8f9", "fontsize": "13",
            "style": "rounded", "pencolor": "#164e63", "fontname": "DejaVu Sans Bold"}
CL_APP = {"bgcolor": "#0f1d33", "fontcolor": "#93c5fd", "fontsize": "13",
          "style": "rounded", "pencolor": "#1e3a5f", "fontname": "DejaVu Sans Bold"}
CL_AGENT = {"bgcolor": "#1a1033", "fontcolor": "#c4b5fd", "fontsize": "12",
            "style": "dashed,rounded", "pencolor": "#6d28d9", "fontname": "DejaVu Sans Bold"}
CL_DATA = {"bgcolor": "#0f1f15", "fontcolor": "#86efac", "fontsize": "13",
           "style": "rounded", "pencolor": "#166534", "fontname": "DejaVu Sans Bold"}
CL_DEVOPS = {"bgcolor": "#1a0f2e", "fontcolor": "#d8b4fe", "fontsize": "13",
             "style": "rounded", "pencolor": "#581c87", "fontname": "DejaVu Sans Bold"}
CL_OBS = {"bgcolor": "#0a1f12", "fontcolor": "#4ade80", "fontsize": "13",
          "style": "rounded", "pencolor": "#15803d", "fontname": "DejaVu Sans Bold"}

# Edge styles
E_HTTPS = {"color": "#22c55e", "style": "bold", "penwidth": "2.0"}
E_INTERNAL = {"color": "#3b82f6", "style": "bold", "penwidth": "1.5"}
E_DATA = {"color": "#f59e0b", "style": "bold", "penwidth": "1.5"}
E_OTLP = {"color": "#10b981", "style": "dashed", "penwidth": "1.5"}
E_AGENT = {"color": "#a78bfa", "style": "bold", "penwidth": "2.0"}
E_INFRA = {"color": "#06b6d4", "style": "dotted", "penwidth": "1.2"}
E_DEVOPS = {"color": "#c084fc", "style": "dashed", "penwidth": "1.2"}


def generate():
    """Generate the architecture diagram."""
    print("Downloading custom icons...")
    icons = download_icons()

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating diagram...")

    with Diagram(
        "Travel Planner — Kubernetes Platform Architecture",
        filename=OUTPUT_FILE,
        outformat="png",
        show=False,
        direction="TB",
        graph_attr=GRAPH_ATTR,
        node_attr=NODE_ATTR,
    ):
        # ── External ────────────────────────────────────────────────
        user = User("User\n(Browser)")

        with Cluster("Kubernetes Cluster — Surface Book 3\nUbuntu 24.04 · K8s 1.35 · GTX 1660 Ti 6GB",
                      graph_attr={**CL_INFRA, "fontsize": "15"}):

            # ── Ingress Layer ───────────────────────────────────────
            with Cluster("Network Edge", graph_attr=CL_INFRA):
                ingress = Nginx("ingress-nginx\n192.168.60.241")
                coredns = Service("CoreDNS LAN\n192.168.60.242\n*.maf.local")
                certmgr = CertManager("cert-manager\nWildcard TLS\n*.maf.local")
                metallb = custom_or_fallback(icons, "metallb",
                                             "MetalLB\nL2 Pool\n.240-.250")

            # ── Application Stack ───────────────────────────────────
            with Cluster("Application Stack — namespace: maflocal", graph_attr=CL_APP):
                frontend = Nextjs("travel-frontend\nNext.js 14\n:3000")
                api = Fastapi("travel-api\nFastAPI + Uvicorn\n:8000")
                mcp = Deploy("mcp-server\nFastMCP 3.0\n:8090")

            # ── MAF Agent Pipeline ──────────────────────────────────
            with Cluster("MAF SequentialBuilder Pipeline", graph_attr=CL_AGENT):
                researcher = Pod("① Researcher\nLLM-only\nDestination research")
                weather = Pod("② WeatherAnalyst\nLLM + MCP tools\nWeather · Time · Food")
                planner = Pod("③ Planner\nLLM-only\n3-day itinerary")

            # ── AI & Data ───────────────────────────────────────────
            with Cluster("AI & Data Layer", graph_attr=CL_DATA):
                ollama = custom_or_fallback(icons, "ollama",
                                            "Ollama\nqwen2.5:7b\n:11434 (GPU)")
                postgres = PostgreSQL("PostgreSQL 16\ntravelplanner\n:5432")
                pv_ollama = PV("PV: ollama-models")
                pv_pg = PV("PV: postgres-data")

            # ── Observability ───────────────────────────────────────
            with Cluster("Observability", graph_attr=CL_OBS):
                aspire = Dotnet("Aspire Dashboard\nOTLP gRPC :18889\nUI :18888")
                grafana = Grafana("Grafana\n:3000")
                prometheus = Prometheus("Prometheus\n:9090")

            # ── DevOps Platform ─────────────────────────────────────
            with Cluster("DevOps Platform", graph_attr=CL_DEVOPS):
                gitea = Gitea("Gitea\nGit Server")
                nexus = Deploy("Nexus\nContainer Registry")
                argocd = ArgoCD("ArgoCD\nGitOps CD")

            # ── Infrastructure ──────────────────────────────────────
            with Cluster("Cluster Infrastructure", graph_attr=CL_INFRA):
                flannel = custom_or_fallback(icons, "flannel",
                                             "Flannel CNI\n10.244.0.0/16")
                nvidia = DaemonSet("NVIDIA Plugin\nGTX 1660 Ti")
                localpath = StorageClass("local-path\nprovisioner")

        # ════════════════════════════════════════════════════════════
        # EDGES
        # ════════════════════════════════════════════════════════════

        # User → Ingress
        user >> Edge(label="HTTPS\n*.maf.local", **E_HTTPS) >> ingress

        # Infra support
        coredns - Edge(**E_INFRA) - ingress
        certmgr >> Edge(label="TLS certs", **E_INFRA) >> ingress
        metallb >> Edge(label="VIP", **E_INFRA) >> ingress
        metallb >> Edge(label="VIP", **E_INFRA) >> coredns

        # Ingress → App services
        ingress >> Edge(label="maflocal.maf.local", **E_INTERNAL) >> frontend
        ingress >> Edge(label="maflocal.maf.local/api", **E_INTERNAL) >> api
        ingress >> Edge(label="aspire.maf.local", **E_INTERNAL) >> aspire

        # Frontend → API
        frontend >> Edge(label="REST + SSE\n/api/*", **E_INTERNAL) >> api

        # API → Data/AI
        api >> Edge(label="LLM inference\nqwen2.5:7b", **E_DATA) >> ollama
        api >> Edge(label="asyncpg\nCRUD", **E_DATA) >> postgres
        api >> Edge(label="Streamable HTTP\n/mcp", **E_INTERNAL) >> mcp

        # MAF Pipeline (sequential)
        api >> Edge(label="run_workflow()", **E_AGENT) >> researcher
        researcher >> Edge(label="shared context", **E_AGENT) >> weather
        weather >> Edge(label="shared context", **E_AGENT) >> planner

        # WeatherAnalyst → MCP tools
        weather >> Edge(label="get_weather\nget_current_time\nsearch_restaurants",
                        **E_INTERNAL) >> mcp

        # Storage
        ollama - Edge(**E_DATA) - pv_ollama
        postgres - Edge(**E_DATA) - pv_pg
        localpath >> Edge(**E_INFRA) >> pv_ollama
        localpath >> Edge(**E_INFRA) >> pv_pg

        # GPU
        nvidia >> Edge(label="nvidia.com/gpu", **E_INFRA) >> ollama

        # OTLP telemetry
        api >> Edge(label="OTLP gRPC", **E_OTLP) >> aspire
        mcp >> Edge(label="OTLP gRPC", **E_OTLP) >> aspire

        # Monitoring
        prometheus >> Edge(label="scrape", **E_OTLP) >> api
        prometheus >> Edge(label="datasource", **E_OTLP) >> grafana

        # DevOps flows
        gitea >> Edge(label="webhook", **E_DEVOPS) >> argocd
        argocd >> Edge(label="sync manifests", **E_DEVOPS) >> api
        nexus >> Edge(label="pull images", **E_DEVOPS) >> api
        nexus >> Edge(label="pull images", **E_DEVOPS) >> frontend
        nexus >> Edge(label="pull images", **E_DEVOPS) >> mcp

    print(f"✓ Diagram saved to {OUTPUT_FILE}.png")


if __name__ == "__main__":
    generate()
