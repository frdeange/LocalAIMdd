"""
Generate Travel Planner Platform Architecture Diagram (PIL version)
Creates a pixel-perfect PNG with dark theme, no external dependencies
beyond Pillow.

Architecture: Full Kubernetes cluster on Surface Book 3 (single-node)
running MAF multi-agent travel planner with Ollama local LLM.

Usage:
    pip install Pillow
    python docs/generate_architecture_png.py

Output:
    docs/images/travel_planner_architecture_pil.png
"""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ── Paths ───────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
IMAGES_DIR = SCRIPT_DIR / "images"
OUTPUT = IMAGES_DIR / "travel_planner_architecture_pil.png"

# ── Canvas dimensions ───────────────────────────────────────────────
WIDTH = 1800
HEIGHT = 1050

# ── Color palette ───────────────────────────────────────────────────
BG = (15, 23, 42)              # slate-900
CLUSTER_BG = (20, 30, 50)     # slightly lighter
TITLE_COLOR = (226, 232, 240)  # slate-200
TEXT_WHITE = (226, 232, 240)
TEXT_GRAY = (148, 163, 184)    # slate-400
TEXT_DIM = (100, 116, 139)     # slate-500

# Service box colors by category
COLORS = {
    "app":     {"bg": (22, 48, 80),  "border": (59, 130, 246),  "icon": (96, 165, 250)},   # blue
    "agent":   {"bg": (46, 16, 80),  "border": (168, 85, 247),  "icon": (196, 181, 253)},  # purple
    "data":    {"bg": (15, 40, 25),  "border": (34, 197, 94),   "icon": (134, 239, 172)},  # green
    "infra":   {"bg": (12, 32, 42),  "border": (6, 182, 212),   "icon": (103, 232, 249)},  # cyan
    "devops":  {"bg": (38, 15, 55),  "border": (168, 85, 247),  "icon": (216, 180, 254)},  # violet
    "obs":     {"bg": (10, 35, 20),  "border": (16, 185, 129),  "icon": (52, 211, 153)},   # emerald
    "user":    {"bg": (30, 41, 59),  "border": (148, 163, 184), "icon": (226, 232, 240)},  # gray
}

ARROW_COLOR = (96, 165, 250)        # blue-400
ARROW_AGENT = (168, 85, 247)        # purple-500
ARROW_DATA = (245, 158, 11)         # amber-500
ARROW_OTLP = (16, 185, 129)        # emerald-500
ARROW_INFRA = (6, 182, 212)         # cyan-500

# ── Fonts ───────────────────────────────────────────────────────────
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
]


def load_font(size, bold=False):
    """Load a font, trying DejaVu then falling back to default."""
    idx = 0 if bold else 1
    for path in [FONT_PATHS[idx]] + FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


FONT_TITLE = load_font(26, bold=True)
FONT_SUBTITLE = load_font(14)
FONT_BOX_TITLE = load_font(13, bold=True)
FONT_BOX_SUB = load_font(10)
FONT_LABEL = load_font(9)
FONT_LEGEND = load_font(10, bold=True)
FONT_LEGEND_TEXT = load_font(9)
FONT_SECTION = load_font(14, bold=True)


# ═══════════════════════════════════════════════════════════════════
# Drawing helpers
# ═══════════════════════════════════════════════════════════════════

def draw_rounded_rect(draw, xy, radius, fill=None, outline=None, width=1):
    """Draw a rounded rectangle."""
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_section_bg(draw, x, y, w, h, label, color_key="app"):
    """Draw a section background with label."""
    colors = COLORS[color_key]
    draw_rounded_rect(draw, (x, y, x + w, y + h), radius=12,
                      fill=colors["bg"], outline=colors["border"], width=1)
    draw.text((x + 12, y + 6), label, fill=colors["border"], font=FONT_SECTION)


def draw_service_box(draw, x, y, w, h, title, subtitle="",
                     category="app", icon_type="default"):
    """Draw a service box with icon, title and subtitle."""
    colors = COLORS[category]
    draw_rounded_rect(draw, (x, y, x + w, y + h), radius=8,
                      fill=colors["bg"], outline=colors["border"], width=2)

    # Icon area
    cx = x + w // 2
    iy = y + 22

    _draw_icon(draw, cx, iy, icon_type, colors["icon"], colors["border"])

    # Title (centered)
    title_bbox = draw.textbbox((0, 0), title, font=FONT_BOX_TITLE)
    tw = title_bbox[2] - title_bbox[0]
    draw.text((x + (w - tw) // 2, y + 42), title, fill=TEXT_WHITE, font=FONT_BOX_TITLE)

    # Subtitle lines (centered)
    if subtitle:
        lines = subtitle.split("\n")
        sy = y + 58
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=FONT_BOX_SUB)
            lw = bbox[2] - bbox[0]
            draw.text((x + (w - lw) // 2, sy), line, fill=TEXT_GRAY, font=FONT_BOX_SUB)
            sy += 13


def _draw_icon(draw, cx, cy, icon_type, color, border):
    """Draw a geometric icon centered at (cx, cy)."""
    if icon_type == "user":
        # Head + body
        draw.ellipse((cx - 8, cy - 12, cx + 8, cy + 2), fill=color)
        draw.arc((cx - 14, cy + 2, cx + 14, cy + 18), 180, 0, fill=color, width=3)
    elif icon_type == "web":
        # Browser window
        draw.rectangle((cx - 16, cy - 10, cx + 16, cy + 10), outline=color, width=2)
        draw.line((cx - 16, cy - 4, cx + 16, cy - 4), fill=color, width=1)
        draw.ellipse((cx - 13, cy - 9, cx - 10, cy - 6), fill=(255, 95, 87))
        draw.ellipse((cx - 8, cy - 9, cx - 5, cy - 6), fill=(254, 188, 46))
        draw.ellipse((cx - 3, cy - 9, cx, cy - 6), fill=(40, 200, 64))
    elif icon_type == "api":
        # Gear/cog simplified
        draw.rectangle((cx - 14, cy - 10, cx + 14, cy + 10), outline=color, width=2)
        draw.text((cx - 11, cy - 8), "API", fill=color, font=FONT_BOX_SUB)
    elif icon_type == "gpu":
        # Chip
        draw.rectangle((cx - 12, cy - 10, cx + 12, cy + 10), outline=color, width=2)
        for dy in (-6, 0, 6):
            draw.line((cx - 16, cy + dy, cx - 12, cy + dy), fill=color, width=2)
            draw.line((cx + 12, cy + dy, cx + 16, cy + dy), fill=color, width=2)
    elif icon_type == "database":
        # Cylinder
        draw.ellipse((cx - 14, cy - 12, cx + 14, cy - 4), outline=color, width=2)
        draw.line((cx - 14, cy - 8, cx - 14, cy + 8), fill=color, width=2)
        draw.line((cx + 14, cy - 8, cx + 14, cy + 8), fill=color, width=2)
        draw.arc((cx - 14, cy, cx + 14, cy + 12), 0, 180, fill=color, width=2)
    elif icon_type == "ai":
        # Hexagon (AI/ML)
        pts = [(cx, cy - 14), (cx + 12, cy - 7), (cx + 12, cy + 7),
               (cx, cy + 14), (cx - 12, cy + 7), (cx - 12, cy - 7)]
        draw.polygon(pts, outline=color, fill=None)
        draw.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=color)
    elif icon_type == "agent":
        # Brain/neuron
        draw.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), outline=color, width=2)
        draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=color)
        for angle_pts in [(-8, -6), (7, -7), (-6, 8), (8, 6)]:
            ax, ay = angle_pts
            draw.line((cx, cy, cx + ax, cy + ay), fill=color, width=1)
    elif icon_type == "shield":
        # Shield for security/certs
        pts = [(cx, cy - 12), (cx + 12, cy - 6), (cx + 10, cy + 6),
               (cx, cy + 14), (cx - 10, cy + 6), (cx - 12, cy - 6)]
        draw.polygon(pts, outline=color, fill=None)
        draw.line((cx, cy - 4, cx, cy + 6), fill=color, width=2)
        draw.line((cx - 4, cy + 1, cx + 4, cy + 1), fill=color, width=2)
    elif icon_type == "network":
        # Network nodes
        for dx, dy in [(-8, -8), (8, -8), (-8, 8), (8, 8), (0, 0)]:
            draw.ellipse((cx + dx - 3, cy + dy - 3, cx + dx + 3, cy + dy + 3),
                         fill=color)
        draw.line((cx - 8, cy - 8, cx + 8, cy - 8), fill=color, width=1)
        draw.line((cx - 8, cy + 8, cx + 8, cy + 8), fill=color, width=1)
        draw.line((cx - 8, cy - 8, cx - 8, cy + 8), fill=color, width=1)
        draw.line((cx + 8, cy - 8, cx + 8, cy + 8), fill=color, width=1)
        draw.line((cx, cy, cx - 8, cy - 8), fill=color, width=1)
        draw.line((cx, cy, cx + 8, cy + 8), fill=color, width=1)
    elif icon_type == "git":
        # Git branch
        draw.ellipse((cx - 4, cy - 10, cx + 4, cy - 2), outline=color, width=2)
        draw.ellipse((cx - 4, cy + 2, cx + 4, cy + 10), outline=color, width=2)
        draw.line((cx, cy - 2, cx, cy + 2), fill=color, width=2)
    elif icon_type == "registry":
        # Container/box
        draw.rectangle((cx - 14, cy - 8, cx - 2, cy + 4), outline=color, width=1)
        draw.rectangle((cx + 2, cy - 8, cx + 14, cy + 4), outline=color, width=1)
        draw.rectangle((cx - 6, cy + 5, cx + 6, cy + 12), outline=color, width=1)
    elif icon_type == "chart":
        # Bar chart (monitoring)
        draw.rectangle((cx - 12, cy + 2, cx - 6, cy + 10), fill=color)
        draw.rectangle((cx - 3, cy - 6, cx + 3, cy + 10), fill=color)
        draw.rectangle((cx + 6, cy - 2, cx + 12, cy + 10), fill=color)
    elif icon_type == "trace":
        # Trace/span lines
        draw.line((cx - 14, cy - 6, cx + 14, cy - 6), fill=color, width=2)
        draw.line((cx - 8, cy, cx + 10, cy), fill=color, width=2)
        draw.line((cx - 4, cy + 6, cx + 14, cy + 6), fill=color, width=2)
        draw.ellipse((cx - 16, cy - 8, cx - 12, cy - 4), fill=color)
        draw.ellipse((cx - 10, cy - 2, cx - 6, cy + 2), fill=color)
        draw.ellipse((cx - 6, cy + 4, cx - 2, cy + 8), fill=color)
    elif icon_type == "mcp":
        # Tool/wrench
        draw.rectangle((cx - 12, cy - 10, cx + 12, cy + 10), outline=color, width=2)
        draw.text((cx - 12, cy - 7), "MCP", fill=color, font=FONT_BOX_SUB)
    elif icon_type == "storage":
        # Disk/drive
        draw.rectangle((cx - 14, cy - 8, cx + 14, cy + 8), outline=color, width=2)
        draw.line((cx - 14, cy, cx + 14, cy), fill=color, width=1)
        draw.ellipse((cx + 6, cy + 2, cx + 10, cy + 6), fill=color)
    else:
        # Default box
        draw.rectangle((cx - 14, cy - 10, cx + 14, cy + 10), outline=color, width=2)


def draw_arrow(draw, x1, y1, x2, y2, color=ARROW_COLOR, label="",
               dashed=False, label_offset=(0, 0)):
    """Draw an arrow from (x1,y1) to (x2,y2) with optional label."""
    # Draw line
    if dashed:
        _draw_dashed_line(draw, x1, y1, x2, y2, color, width=2, dash_len=8)
    else:
        draw.line((x1, y1, x2, y2), fill=color, width=2)

    # Arrowhead
    import math
    angle = math.atan2(y2 - y1, x2 - x1)
    size = 8
    ax1 = x2 - size * math.cos(angle - 0.4)
    ay1 = y2 - size * math.sin(angle - 0.4)
    ax2 = x2 - size * math.cos(angle + 0.4)
    ay2 = y2 - size * math.sin(angle + 0.4)
    draw.polygon([(x2, y2), (int(ax1), int(ay1)), (int(ax2), int(ay2))], fill=color)

    # Label
    if label:
        mx = (x1 + x2) // 2 + label_offset[0]
        my = (y1 + y2) // 2 + label_offset[1] - 8
        draw.text((mx, my), label, fill=TEXT_DIM, font=FONT_LABEL)


def _draw_dashed_line(draw, x1, y1, x2, y2, color, width=2, dash_len=8):
    """Draw a dashed line."""
    import math
    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)
    if dist == 0:
        return
    steps = int(dist / dash_len)
    for i in range(0, steps, 2):
        sx = x1 + dx * i / steps
        sy = y1 + dy * i / steps
        ex = x1 + dx * min(i + 1, steps) / steps
        ey = y1 + dy * min(i + 1, steps) / steps
        draw.line((int(sx), int(sy), int(ex), int(ey)), fill=color, width=width)


def draw_legend(draw, x, y):
    """Draw a color legend for service categories."""
    draw_rounded_rect(draw, (x, y, x + 250, y + 160), radius=8,
                      fill=(20, 28, 45), outline=(51, 65, 85), width=1)
    draw.text((x + 10, y + 8), "Legend", fill=TEXT_WHITE, font=FONT_LEGEND)

    items = [
        ("Application Services", COLORS["app"]["border"]),
        ("MAF Agent Pipeline", COLORS["agent"]["border"]),
        ("AI & Data Layer", COLORS["data"]["border"]),
        ("Infrastructure", COLORS["infra"]["border"]),
        ("DevOps Platform", COLORS["devops"]["border"]),
        ("Observability", COLORS["obs"]["border"]),
    ]
    ly = y + 28
    for label, color in items:
        draw.rectangle((x + 12, ly + 2, x + 24, ly + 12), fill=color)
        draw.text((x + 30, ly), label, fill=TEXT_GRAY, font=FONT_LEGEND_TEXT)
        ly += 20


# ═══════════════════════════════════════════════════════════════════
# Main generation
# ═══════════════════════════════════════════════════════════════════

def generate():
    """Generate the PIL architecture diagram."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    # ── Title ───────────────────────────────────────────────────────
    draw.text((40, 20), "Travel Planner — Kubernetes Platform Architecture",
              fill=TITLE_COLOR, font=FONT_TITLE)
    draw.text((40, 54),
              "Surface Book 3 · Ubuntu 24.04 · K8s 1.35 · GTX 1660 Ti 6GB · "
              "MAF SequentialBuilder · Ollama qwen2.5:7b",
              fill=TEXT_DIM, font=FONT_SUBTITLE)

    # ── Layout coordinates ──────────────────────────────────────────
    # BOX = (x, y, w, h)
    BOX_W, BOX_H = 140, 90
    BOX_W_L, BOX_H_L = 160, 95  # larger boxes

    # Row 0 — User + Ingress Layer (y=85)
    R0 = 90
    user_box = (40, R0, 110, BOX_H)
    ingress_box = (260, R0, BOX_W, BOX_H)
    coredns_box = (430, R0, BOX_W, BOX_H)
    certmgr_box = (600, R0, BOX_W, BOX_H)
    metallb_box = (770, R0, BOX_W, BOX_H)

    # Section bg: Network Edge
    draw_section_bg(draw, 245, R0 - 22, 680, BOX_H + 30, "Network Edge (LAN)", "infra")

    draw_service_box(draw, *user_box, "User", "Browser\n(LAN / Mobile)", "user", "user")
    draw_service_box(draw, *ingress_box, "ingress-nginx", "192.168.60.241\nTLS termination", "infra", "network")
    draw_service_box(draw, *coredns_box, "CoreDNS LAN", "192.168.60.242\n*.maf.local", "infra", "network")
    draw_service_box(draw, *certmgr_box, "cert-manager", "Wildcard TLS\n*.maf.local (10yr)", "infra", "shield")
    draw_service_box(draw, *metallb_box, "MetalLB", "L2 Mode\nPool .240-.250", "infra", "network")

    # Row 1 — Application Stack (y=230)
    R1 = 230
    draw_section_bg(draw, 245, R1 - 22, 500, BOX_H_L + 30,
                    "Application Stack — ns: maflocal", "app")

    frontend_box = (260, R1, BOX_W_L, BOX_H_L)
    api_box = (440, R1, BOX_W_L, BOX_H_L)
    mcp_box = (620, R1, BOX_W_L, BOX_H_L)

    draw_service_box(draw, *frontend_box, "travel-frontend", "Next.js 14\nStandalone :3000", "app", "web")
    draw_service_box(draw, *api_box, "travel-api", "FastAPI + Uvicorn\nOTel instrumented :8000", "app", "api")
    draw_service_box(draw, *mcp_box, "mcp-server", "FastMCP 3.0\nStreamable HTTP :8090", "app", "mcp")

    # Row 1b — MAF Pipeline (y=230, right side)
    draw_section_bg(draw, 850, R1 - 22, 920, BOX_H_L + 30,
                    "MAF SequentialBuilder Pipeline (inside travel-api)", "agent")

    ag_w, ag_h = 165, BOX_H_L
    r_box = (870, R1, ag_w, ag_h)
    w_box = (1090, R1, ag_w + 30, ag_h)
    p_box = (1370, R1, ag_w, ag_h)

    draw_service_box(draw, *r_box, "① Researcher", "LLM-only\nAttractions, culture\ntransport, tips", "agent", "agent")
    draw_service_box(draw, *w_box, "② WeatherAnalyst", "LLM + MCP tools\nWeather, time\nrestaurants", "agent", "ai")
    draw_service_box(draw, *p_box, "③ Planner", "LLM-only\n3-day itinerary\nbudget, packing", "agent", "agent")

    # Row 2 — AI & Data (y=385)
    R2 = 385
    draw_section_bg(draw, 245, R2 - 22, 680, BOX_H_L + 30,
                    "AI & Data Layer", "data")

    ollama_box = (260, R2, BOX_W_L, BOX_H_L)
    pg_box = (440, R2, BOX_W_L, BOX_H_L)
    pv1_box = (620, R2, BOX_W, 70)
    pv2_box = (780, R2, BOX_W, 70)

    draw_service_box(draw, *ollama_box, "Ollama", "qwen2.5:7b (4.7 GB)\nGPU :11434", "data", "gpu")
    draw_service_box(draw, *pg_box, "PostgreSQL 16", "travelplanner DB\nasyncpg :5432", "data", "database")
    draw_service_box(draw, *pv1_box, "PV: ollama-models", "Persistent Volume", "data", "storage")
    draw_service_box(draw, *pv2_box, "PV: postgres-data", "Persistent Volume", "data", "storage")

    # Row 2 right — Observability
    draw_section_bg(draw, 980, R2 - 22, 790, BOX_H_L + 30,
                    "Observability", "obs")

    aspire_box = (1000, R2, BOX_W_L + 20, BOX_H_L)
    grafana_box = (1210, R2, BOX_W, BOX_H_L)
    prom_box = (1370, R2, BOX_W, BOX_H_L)

    draw_service_box(draw, *aspire_box, "Aspire Dashboard", "OTLP gRPC :18889\nUI :18888", "obs", "trace")
    draw_service_box(draw, *grafana_box, "Grafana", "Dashboards\n:3000", "obs", "chart")
    draw_service_box(draw, *prom_box, "Prometheus", "Metrics\n:9090", "obs", "chart")

    # Row 3 — DevOps + Infrastructure (y=540)
    R3 = 540
    draw_section_bg(draw, 245, R3 - 22, 400, BOX_H + 30,
                    "DevOps Platform", "devops")

    gitea_box = (260, R3, BOX_W - 10, BOX_H)
    nexus_box = (390, R3, BOX_W - 10, BOX_H)
    argo_box = (520, R3, BOX_W - 10, BOX_H)

    draw_service_box(draw, *gitea_box, "Gitea", "Git Server", "devops", "git")
    draw_service_box(draw, *nexus_box, "Nexus", "Container\nRegistry", "devops", "registry")
    draw_service_box(draw, *argo_box, "ArgoCD", "GitOps\nCD", "devops", "git")

    draw_section_bg(draw, 700, R3 - 22, 640, BOX_H + 30,
                    "Cluster Infrastructure", "infra")

    flannel_box = (720, R3, BOX_W - 10, BOX_H)
    nvidia_box = (850, R3, BOX_W - 10, BOX_H)
    lp_box = (980, R3, BOX_W + 10, BOX_H)
    node_box = (1130, R3, BOX_W + 30, BOX_H)

    draw_service_box(draw, *flannel_box, "Flannel CNI", "10.244.0.0/16", "infra", "network")
    draw_service_box(draw, *nvidia_box, "NVIDIA Plugin", "GTX 1660 Ti\n6GB VRAM", "infra", "gpu")
    draw_service_box(draw, *lp_box, "local-path", "Provisioner\nDynamic PVC", "infra", "storage")
    draw_service_box(draw, *node_box, "K8s Node", "Control + Worker\nkubeadm 1.35", "infra", "network")

    # ════════════════════════════════════════════════════════════════
    # ARROWS
    # ════════════════════════════════════════════════════════════════

    def box_center(bx):
        return (bx[0] + bx[2] // 2, bx[1] + bx[3] // 2)

    def box_right(bx):
        return (bx[0] + bx[2], bx[1] + bx[3] // 2)

    def box_left(bx):
        return (bx[0], bx[1] + bx[3] // 2)

    def box_bottom(bx):
        return (bx[0] + bx[2] // 2, bx[1] + bx[3])

    def box_top(bx):
        return (bx[0] + bx[2] // 2, bx[1])

    # User → Ingress
    draw_arrow(draw, *box_right(user_box), *box_left(ingress_box),
               color=(34, 197, 94), label="HTTPS", label_offset=(0, -4))

    # Ingress → Frontend (down)
    draw_arrow(draw, ingress_box[0] + 50, ingress_box[1] + ingress_box[3],
               frontend_box[0] + 50, frontend_box[1],
               label="maflocal\n.maf.local", label_offset=(-50, -4))

    # Ingress → API (down)
    draw_arrow(draw, ingress_box[0] + 100, ingress_box[1] + ingress_box[3],
               api_box[0] + 80, api_box[1],
               label="/api", label_offset=(5, -4))

    # Frontend → API
    draw_arrow(draw, *box_right(frontend_box), *box_left(api_box),
               label="REST + SSE", label_offset=(-5, -10))

    # API → MCP
    draw_arrow(draw, *box_right(api_box), *box_left(mcp_box),
               label="HTTP /mcp", label_offset=(-5, -10))

    # API → MAF Pipeline (right)
    draw_arrow(draw, api_box[0] + api_box[2], api_box[1] + 30,
               r_box[0], r_box[1] + r_box[3] // 2,
               color=ARROW_AGENT, label="run_workflow()", label_offset=(60, -14))

    # Researcher → WeatherAnalyst → Planner
    draw_arrow(draw, *box_right(r_box), *box_left(w_box),
               color=ARROW_AGENT, label="shared\ncontext", label_offset=(-5, -12))
    draw_arrow(draw, *box_right(w_box), *box_left(p_box),
               color=ARROW_AGENT, label="shared\ncontext", label_offset=(-5, -12))

    # WeatherAnalyst → MCP (down-left connection)
    draw_arrow(draw, w_box[0] + w_box[2] // 2, w_box[1] + w_box[3],
               mcp_box[0] + mcp_box[2] // 2, mcp_box[1],
               color=ARROW_COLOR, label="get_weather\nget_current_time\nsearch_restaurants",
               label_offset=(-80, -15), dashed=False)

    # API → Ollama (down)
    draw_arrow(draw, api_box[0] + 40, api_box[1] + api_box[3],
               ollama_box[0] + 80, ollama_box[1],
               color=ARROW_DATA, label="LLM inference", label_offset=(-70, -4))

    # API → PostgreSQL (down)
    draw_arrow(draw, api_box[0] + 120, api_box[1] + api_box[3],
               pg_box[0] + 80, pg_box[1],
               color=ARROW_DATA, label="asyncpg", label_offset=(5, -4))

    # Ollama → PV
    draw_arrow(draw, *box_right(ollama_box), *box_left(pv1_box),
               color=ARROW_DATA, dashed=True)

    # Postgres → PV
    draw_arrow(draw, *box_right(pg_box), *box_left(pv2_box),
               color=ARROW_DATA, dashed=True)

    # API → Aspire (OTLP)
    draw_arrow(draw, api_box[0] + api_box[2] - 20, api_box[1] + api_box[3],
               aspire_box[0] + 40, aspire_box[1],
               color=ARROW_OTLP, label="OTLP gRPC", label_offset=(70, 20), dashed=True)

    # MCP → Aspire (OTLP)
    draw_arrow(draw, mcp_box[0] + mcp_box[2] - 20, mcp_box[1] + mcp_box[3],
               aspire_box[0] + 80, aspire_box[1],
               color=ARROW_OTLP, label="OTLP gRPC", label_offset=(30, 20), dashed=True)

    # Prometheus → Grafana
    draw_arrow(draw, *box_left(prom_box), *box_right(grafana_box),
               color=ARROW_OTLP, label="datasource", label_offset=(-15, -12))

    # NVIDIA → Ollama
    draw_arrow(draw, nvidia_box[0] + nvidia_box[2] // 2, nvidia_box[1],
               ollama_box[0] + ollama_box[2] // 2, ollama_box[1] + ollama_box[3],
               color=ARROW_INFRA, label="nvidia.com/gpu", label_offset=(-75, 0),
               dashed=True)

    # Gitea → ArgoCD
    draw_arrow(draw, *box_right(gitea_box), *box_left(argo_box),
               color=(168, 85, 247), label="webhook", label_offset=(10, -12))

    # Nexus → upward (pull images) — just a label
    draw_arrow(draw, nexus_box[0] + nexus_box[2] // 2, nexus_box[1],
               api_box[0] + 20, api_box[1] + api_box[3],
               color=(168, 85, 247), label="pull images",
               label_offset=(-60, 15), dashed=True)

    # ── Ingress hostname labels (right side) ────────────────────────
    info_x = 1400
    info_y = R0 - 10
    draw_rounded_rect(draw, (info_x, info_y, info_x + 370, info_y + 140),
                      radius=8, fill=(20, 28, 45), outline=(51, 65, 85), width=1)
    draw.text((info_x + 10, info_y + 8), "Ingress Hostnames (TLS)",
              fill=TEXT_WHITE, font=FONT_LEGEND)
    hostnames = [
        ("maflocal.maf.local", "Frontend + API"),
        ("aspire.maf.local", "Aspire Dashboard"),
        ("gitea.maf.local", "Gitea"),
        ("nexus.maf.local", "Nexus Registry"),
        ("argocd.maf.local", "ArgoCD"),
        ("grafana.maf.local", "Grafana"),
    ]
    hy = info_y + 28
    for host, desc in hostnames:
        draw.text((info_x + 12, hy), f"→ {host}", fill=ARROW_COLOR, font=FONT_LABEL)
        draw.text((info_x + 210, hy), desc, fill=TEXT_DIM, font=FONT_LABEL)
        hy += 17

    # ── SSE Event Protocol (bottom right) ───────────────────────────
    sse_x = 1400
    sse_y = R3 - 22
    draw_rounded_rect(draw, (sse_x, sse_y, sse_x + 370, sse_y + 130),
                      radius=8, fill=(20, 28, 45), outline=(51, 65, 85), width=1)
    draw.text((sse_x + 10, sse_y + 8), "SSE Event Protocol",
              fill=TEXT_WHITE, font=FONT_LEGEND)
    events = [
        "workflow_started → { workflow: 'travel_planner' }",
        "agent_started    → { agent, step }",
        "agent_completed  → { agent, step, output }",
        "  ↻ repeat for each agent (3 steps)",
        "workflow_completed → { final_output }",
    ]
    ey = sse_y + 28
    for evt in events:
        draw.text((sse_x + 12, ey), evt, fill=TEXT_GRAY, font=FONT_LABEL)
        ey += 18

    # ── Legend ──────────────────────────────────────────────────────
    draw_legend(draw, 40, HEIGHT - 180)

    # ── Copyright ──────────────────────────────────────────────────
    draw.text((40, HEIGHT - 18),
              "Travel Planner PoC — MAF + Ollama on Kubernetes · Feb 2026",
              fill=TEXT_DIM, font=FONT_LABEL)

    # ── Save ───────────────────────────────────────────────────────
    img.save(str(OUTPUT), "PNG", optimize=True)
    print(f"✓ Diagram saved to {OUTPUT}")


if __name__ == "__main__":
    generate()
