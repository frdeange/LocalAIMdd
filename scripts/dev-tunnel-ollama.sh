#!/bin/bash
# ─────────────────────────────────────────────────────────
# Túnel temporal a Ollama para pruebas locales
# ─────────────────────────────────────────────────────────
# - NO modifica nada en el cluster
# - NO afecta a los pods que ya consumen Ollama
# - Se cierra limpiamente con Ctrl+C
# ─────────────────────────────────────────────────────────

set -euo pipefail

NAMESPACE="shared-services"
SERVICE="svc/ollama"
LOCAL_PORT=11434
REMOTE_PORT=11434

# Comprobar que kubectl está disponible
if ! command -v kubectl &>/dev/null; then
    echo "❌ kubectl no encontrado en PATH"
    exit 1
fi

# Comprobar que el servicio existe
if ! kubectl get "$SERVICE" -n "$NAMESPACE" &>/dev/null; then
    echo "❌ No se encuentra $SERVICE en namespace $NAMESPACE"
    exit 1
fi

# Comprobar que el puerto local no está ya ocupado
if lsof -i :"$LOCAL_PORT" &>/dev/null; then
    echo "⚠️  El puerto $LOCAL_PORT ya está en uso. ¿Ya hay un túnel abierto?"
    echo "   Puedes verificar con: lsof -i :$LOCAL_PORT"
    exit 1
fi

# Limpiar al salir (Ctrl+C o cierre)
cleanup() {
    echo ""
    echo "🔌 Túnel cerrado. El cluster sigue intacto."
    exit 0
}
trap cleanup SIGINT SIGTERM

echo "🔗 Abriendo túnel a Ollama..."
echo "   Cluster:  $SERVICE.$NAMESPACE → :$REMOTE_PORT"
echo "   Local:    http://localhost:$LOCAL_PORT"
echo ""
echo "   Prueba rápida (en otra terminal):"
echo "     curl http://localhost:$LOCAL_PORT/api/tags"
echo ""
echo "   Usar modelo:"
echo "     curl http://localhost:$LOCAL_PORT/api/generate -d '{\"model\":\"qwen2.5:7b\",\"prompt\":\"Hola\",\"stream\":false}'"
echo ""
echo "   Ctrl+C para cerrar"
echo "───────────────────────────────────────"

# Abrir el túnel (se queda en foreground, Ctrl+C lo cierra)
kubectl port-forward -n "$NAMESPACE" "$SERVICE" "$LOCAL_PORT:$REMOTE_PORT"