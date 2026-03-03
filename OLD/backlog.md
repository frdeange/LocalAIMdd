# Backlog: Entorno 100% Contenerizado con Ollama

> Plan diseñado el 20 de febrero de 2026.
> Objetivo: migrar el proyecto a un nuevo repo donde **todo** corra en contenedores (sin dependencias en el host), listo para Kubernetes y entornos air-gapped.

## Contexto

Azure AI Foundry Local es una app nativa que no soporta contenedores. Para lograr un entorno 100% desconectado y portable, reemplazamos Foundry Local por **Ollama en Docker** como servidor de inferencia. MAF ya incluye `OllamaChatClient`, así que el cambio de código es mínimo (solo 2 archivos).

## Decisiones Tomadas

| Decisión | Elegido | Alternativa descartada | Razón |
|----------|---------|----------------------|-------|
| Servidor de inferencia | **Ollama en Docker** | Foundry Local containerizado | Foundry Local no soporta contenedores oficialmente. Ollama tiene imagen Docker oficial, API OpenAI-compatible, soporte GPU/CPU |
| Cliente MAF | **`OllamaChatClient`** | `OpenAIChatClient` genérico | MAF incluye cliente nativo Ollama con opciones específicas (`num_ctx`, `num_gpu`, `keep_alive`) |
| Modelo | **Configurable por env var** | Hardcoded Phi-4-mini | Phi-4-mini disponible en Ollama, pero abierto a Llama 3, Mistral, etc. |
| Infra primaria | **Docker Compose** | Kubernetes directo | Docker Compose para desarrollo/validación. Diseño 1:1 mapeable a K8s después |
| GPU | **Soporte dual GPU/CPU** | Solo GPU | Perfiles Docker Compose para ambos escenarios |

## Hallazgos Clave de la Investigación

- **`FoundryLocalClient` es internamente un `AsyncOpenAI` client** apuntando a localhost — el swap a Ollama es trivial
- **Los agentes tipan `client` como `object`** y llaman `.as_agent()` — cualquier `BaseChatClient` funciona como drop-in replacement
- **`OllamaChatClient` ya está instalado** como dependencia transitiva de MAF
- **Solo 2 archivos de código cambian**: `main.py` y `src/config.py`. Agentes, workflows, MCP tools y telemetría quedan intactos
- **Los nombres de servicio Docker** (`ollama`, `mcp-server`, `aspire-dashboard`) se convierten directamente en Services de K8s

## Plan de Implementación

### Paso 1: Añadir servicio Ollama al `docker-compose.yml`

- Imagen oficial `ollama/ollama`
- Puerto `11434:11434` (API OpenAI-compatible)
- Volume persistente para modelos: `ollama-models:/root/.ollama`
- Dos perfiles: `gpu` (con `deploy.resources.reservations.devices` para NVIDIA GPU) y `cpu` (sin GPU, modelos cuantizados)
- Health check contra `/api/tags`
- Script de init que haga `ollama pull <modelo>` al arrancar

### Paso 2: Crear script de inicialización de modelos (`scripts/init-ollama.sh`)

- Arranca el servidor Ollama en background
- Ejecuta `ollama pull phi4-mini` (o modelo configurado)
- Espera a que el modelo esté listo
- Mantiene el servidor en foreground
- Para air-gapped: el volumen se pre-carga una vez y funciona offline después

### Paso 3: Modificar `src/config.py` — Configuración genérica de LLM

- Nuevos campos: `ollama_host` (default `http://ollama:11434`), `ollama_model_id` (default `phi4-mini`)
- `mcp_server_url` → `http://mcp-server:8090/mcp` (nombre de servicio Docker)
- `otel_endpoint` → `http://aspire-dashboard:18889` (red interna Docker)
- Deprecar/eliminar `foundry_model_id`

### Paso 4: Modificar `main.py` — Reemplazar FoundryLocalClient

```python
# ANTES
from agent_framework_foundry_local import FoundryLocalClient
client = FoundryLocalClient(model_id=settings.foundry_model_id, bootstrap=True, prepare_model=True)

# DESPUÉS
from agent_framework_ollama import OllamaChatClient
client = OllamaChatClient(model_id=settings.ollama_model_id, host=settings.ollama_host)
```

**Nada más cambia** — agentes, workflows, MCP tools y telemetría siguen funcionando.

### Paso 5: Crear Dockerfile para el orquestador (raíz)

- Base: `python:3.13-slim`
- Copiar `requirements.txt`, `main.py`, `src/`
- Instalar dependencias MAF (sin `agent-framework-foundry-local`)
- Entrypoint: `opentelemetry-instrument python main.py`
- No necesita GPU — solo hace llamadas HTTP a Ollama

### Paso 6: Actualizar `requirements.txt`

- Eliminar `agent-framework-foundry-local`
- Añadir `agent-framework-ollama` explícitamente
- Mantener el resto igual

### Paso 7: Actualizar `docker-compose.yml` — Servicio orquestador

- Nuevo servicio `orchestrator` usando Dockerfile de raíz
- `depends_on`: `ollama` (healthy), `mcp-server` (healthy), `aspire-dashboard` (started)
- Variables de entorno: `OLLAMA_HOST`, `OLLAMA_MODEL_ID`, `MCP_SERVER_URL`, `OTEL_*`
- Modo interactivo (`stdin_open: true`, `tty: true`) para input del usuario
- Red compartida con todos los servicios

### Paso 8: Docker Compose profiles para GPU/CPU

- Profile `gpu`: Ollama con NVIDIA runtime y reserva de GPU
- Profile `cpu`: Ollama sin GPU, modelo cuantizado (ej: `phi4-mini:q4_0`)
- Uso: `docker-compose --profile gpu up` o `docker-compose --profile cpu up`
- Alternativa: ficheros override (`docker-compose.gpu.yml`, `docker-compose.cpu.yml`)

### Paso 9: Actualizar documentación

- `README.md`: Eliminar prerequisito de FoundryLocal/NVIDIA GPU. Documentar modos GPU/CPU y comandos docker-compose
- `docs/architecture.md`: Actualizar diagrama con Ollama como serving layer
- Sección "Modo Air-Gapped": cómo pre-cargar modelos y desplegar sin internet

### Paso 10: Diseño para Kubernetes (documentar, no implementar)

| Docker Compose | Kubernetes |
|---------------|-----------|
| Ollama service | Deployment + Service + PVC (`nvidia.com/gpu: 1` si GPU) |
| MCP Server | Deployment + Service |
| Aspire Dashboard | Deployment + Service |
| Orquestador | Job o Deployment |
| Volumes | PersistentVolumeClaims |
| Env vars | ConfigMaps / Secrets |
| Nombres de servicio | Service DNS names (idénticos) |

Documentar en `docs/kubernetes-guide.md`.

## Verificación

- [ ] `docker-compose --profile gpu up` (o `cpu`) arranca los 4 servicios
- [ ] Ollama health check pasa y modelo cargado (`curl http://localhost:11434/api/tags`)
- [ ] Orquestador se conecta a Ollama y ejecuta pipeline de agentes
- [ ] Travel plan generado correctamente
- [ ] Trazas visibles en Aspire Dashboard (`http://localhost:18888`)
- [ ] Test air-gapped: sin internet + volumen pre-cargado → funciona
- [ ] Tests existentes pasan (adaptar los que referencien Foundry Local)

## Arquitectura Destino

```
                    Docker Compose / Kubernetes
┌──────────────────────────────────────────────────────────┐
│                                                          │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────┐  │
│  │   Ollama     │   │  MCP Server  │   │   Aspire     │  │
│  │  (GPU/CPU)   │   │  (FastMCP)   │   │  Dashboard   │  │
│  │  :11434      │   │  :8090       │   │  :18888      │  │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘  │
│         │                  │                  │          │
│         │    ┌─────────────┴──────────────────┘          │
│         │    │                                           │
│  ┌──────┴────┴───────────────────┐                       │
│  │      Orchestrator (MAF)       │                       │
│  │  Researcher → Weather → Plan  │                       │
│  └───────────────────────────────┘                       │
│                                                          │
└──────────────────────────────────────────────────────────┘
         Volume: ollama-models (persistente)
```
