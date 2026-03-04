#!/bin/bash
# ─────────────────────────────────────────────────────────
# Túnel temporal a servicios del cluster para pruebas locales
# ─────────────────────────────────────────────────────────
# - NO modifica nada en el cluster
# - NO afecta a los pods que ya consumen estos servicios
# - Se cierra todo limpiamente con Ctrl+C
# ─────────────────────────────────────────────────────────

set -euo pipefail

# ── Servicios a exponer ──────────────────────────────────
# Formato: "namespace service local_port:remote_port descripcion"
TUNNELS=(
    "shared-services svc/ollama         11434:11434  Ollama-LLM"
    "bms-ops         svc/mcp-bms        8093:8093    MCP-BMS"
    "bms-ops         svc/mcp-camera     8090:8090    MCP-Camera"
    "bms-ops         svc/mcp-weather    8091:8091    MCP-Weather"
    "bms-ops         svc/speech-service  8092:8092    Speech-Service"
    "bms-ops         svc/bms-api        8000:8000    BMS-API"
)

PIDS=()

# Comprobar que kubectl está disponible
if ! command -v kubectl &>/dev/null; then
    echo "❌ kubectl no encontrado en PATH"
    exit 1
fi

# Limpiar todos los túneles al salir (Ctrl+C o cierre)
cleanup() {
    echo ""
    echo "🔌 Cerrando todos los túneles..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null
    echo "✅ Todos los túneles cerrados. El cluster sigue intacto."
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

echo "🔗 Abriendo túneles a servicios del cluster..."
echo "───────────────────────────────────────"

FAILED=0
OPENED=0

for tunnel in "${TUNNELS[@]}"; do
    namespace=$(echo "$tunnel" | awk '{print $1}')
    service=$(echo "$tunnel" | awk '{print $2}')
    ports=$(echo "$tunnel" | awk '{print $3}')
    label=$(echo "$tunnel" | awk '{print $4}')
    local_port=$(echo "$ports" | cut -d':' -f1)

    # Verificar que el servicio existe
    if ! kubectl get "$service" -n "$namespace" &>/dev/null; then
        echo "   ⚠️  $label — $service en $namespace no encontrado"
        FAILED=$((FAILED + 1))
        continue
    fi

    # Verificar que el puerto local está libre
    if lsof -i :"$local_port" &>/dev/null 2>&1; then
        echo "   ⚠️  $label — puerto $local_port ya en uso"
        FAILED=$((FAILED + 1))
        continue
    fi

    # Abrir túnel en background
    kubectl port-forward -n "$namespace" "$service" "$ports" &>/dev/null &
    PIDS+=($!)
    echo "   ✅ $label → http://localhost:$local_port"
    OPENED=$((OPENED + 1))
done

echo "───────────────────────────────────────"
echo ""
echo "📋 Pruebas rápidas (en otra terminal):"
echo ""
echo "   Ollama:          curl http://localhost:11434/api/tags"
echo "   MCP BMS:         curl http://localhost:8093/"
echo "   MCP Camera:      curl http://localhost:8090/"
echo "   MCP Weather:     curl http://localhost:8091/"
echo "   Speech Service:  curl http://localhost:8092/"
echo "   BMS API:         curl http://localhost:8000/docs"
echo ""

if [ "$FAILED" -gt 0 ]; then
    echo "⚠️  $FAILED servicio(s) no pudieron conectarse"
fi

echo "✅ $OPENED túnel(es) abiertos"
echo "   Ctrl+C para cerrar todos"
echo "───────────────────────────────────────"

# Mantener el script vivo hasta Ctrl+C
wait