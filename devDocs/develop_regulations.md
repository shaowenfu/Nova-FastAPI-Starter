# Nova FastAPI Starter · Developer Regulations

Core mantra: first principles + Occam's razor + fail fast. Intent explicit, no hidden fallbacks.

## 1) Framework Map (tree)
```
nova-fastapi-starter/
├── main.py                # lifespan, routers, exceptions, static mount
├── core/                  # config, logger, exceptions, memory scaffold
├── dependencies/          # DI providers (config/auth/token/LLM/SMS/repos)
├── routers/               # HTTP/WS controllers (thin)
├── services/              # business orchestration; baselines in services/basic
├── infrastructure/        # db clients (mongo/redis/mysql), models, repositories
├── static/                # auth guide, WS tester, notifications, index
└── scripts/               # optional utilities
```

## 2) Responsibilities & Boundaries
| Module | Responsibility | Do | Don’t | Depends |
| --- | --- | --- | --- | --- |
| `main.py` | Lifespan, router aggregation, exception wiring, static mount | Init/close DBs, memory, WS once | Business logic, ad-hoc clients | core, routers, infra/db, services/basic/websocket |
| `core/` | Settings, logger, shared exceptions, memory scaffold | Validate config, provide loggers | Business/data access | stdlib |
| `dependencies/` | DI providers | Expose config, ModelService, auth/token/SMS/repos | Instantiate in routers | core, services/basic, infra/repos |
| `routers/` | HTTP/WS controllers | Validate, `Depends`, DTO responses | Business rules, DB/LLM calls | dependencies, services/basic, infra/models |
| `services/basic/` | Auth/LLM/SMS/WS orchestration | Raise `BaseAPIException` subclasses, coordinate repos/LLM/memory | Use `HTTPException`; new clients | core, infra/repos, infra/db |
| `infra/db/` | Client singletons | `connect_*`, `close_*`, `get_*` | Run queries | core/config |
| `infra/repos/` | CRUD-only data access | Return Pydantic models (`DB*`, `*Create`, `*Response`) | Business logic, secrets logging | infra/db, infra/models |
| `infra/models/` | Data contracts | Pydantic models, serialization helpers | Cross-layer logic | stdlib |
| `static/` | Demo pages | Standalone HTML | Backend coupling | none |

## 3) Lifespan & DI
- Startup: setup logger → connect mongo/mysql/redis → init memory adapter → init WebSocketService → serve.
- Shutdown: cleanup WebSocketService → close mongo/redis/mysql → close `ModelService`.
- Singletons: DB clients, `ModelService`, `WebSocketService` created once in lifespan.
- All deps from `dependencies/providers.py`; never `new` in routers/services.

## 4) Coding Standards
- Python 3.11, 4-space indent, full type hints, small focused functions.
- Logging: `core.logger.get_logger`; never reconfigure logging in modules.
- Errors: required config/keys must raise; services use `BaseAPIException` (not `HTTPException`). No silent fallbacks.
- Comments minimal—only for intent/edge cases.

## 5) Auth & Security
- JWT-only; user id from token `sub` only. No header/query user ids.
- WS token via first `Sec-WebSocket-Protocol` (echoed); HTTP via `Authorization: Bearer <token>` or `X-Auth-Token`.
- Secrets live in `.env` (copy from `.env.example`); never commit real keys.

## 6) WebSocket
- Endpoint `/ws/chat`; manager + handlers in `services/basic/websocket.py`.
- Built-ins: `ping`, `status`, `echo`, `llm_stream`; extend at startup via `register_handler("type", handler)`.
- Request `UnifiedWebSocketRequest`: required `type`; optional `agent_id/message/payload/context`; limits from `core/config.py`.
- Fail fast: invalid/oversized → error/close; structured error payloads OK, no hidden downgrades.

## 7) LLM
- OpenAI-compatible wrapper in `services/basic/llm.py`; driven by `DEFAULT_MODEL_PROVIDER` + generic `LLM_` config.
- Always `await`; catch/propagate `LLMServiceError`; never wrap async clients in thread executors.

## 8) Memory (Native Vector Support)
- `core/memory_adapter` provides pluggable persistence.
- Default: **ChromaDB** via `docker-compose.memory.yml`.
- Usage: Set `MEMORY_ENABLED=true`. Use `store_memories` and `fetch_memories` interfaces only.
- Do not couple business logic to specific vector stores; use the adapter.

## 9) Data & Persistence
- Use provided singletons: `get_mysql_session`, `get_redis_client`, mongo helpers. No ad-hoc connections.
- Repos are CRUD-only; no secrets logging; no global state mutation. Services orchestrate.

## 10) Configuration
- Chain: `.env` (from `.env.example`) → docker-compose env_file → `core/config.py`.
- **Generic Keys Only**: Use `LLM_BASE_URL`, `SMS_ACCESS_KEY_ID`. No vendor prefixes (`ALI_SMS`, `DEEPSEEK`).
- Internal hosts use service names (redis/mysql/mongo/chroma). Missing required keys (e.g., JWT secret) must error immediately.

## 11) Runbook
- Local: ensure Redis/Mongo/MySQL (and Chroma if enabled) up; run `python -m uvicorn main:app --reload`.
- Compose: `docker compose up --build`. Add `-f docker-compose.memory.yml` for RAG support.
- Tools: Adminer/Redis Commander available via `--profile ops`.

## 12) Testing & Quality
- pytest + pytest-asyncio; each feature needs ≥1 success + ≥1 failure path.
- Prefer dependency overrides/fakes over real external calls; no happy-path-only tests.
- Follow PEP8; tidy imports; drop unused deps.

## 13) Git & Docs
- Conventional commits (`feat(auth): ...`, `fix(ws): ...`); small scoped changes.
- Update docs/static when adding/removing modules.
- `.env` and secrets are never committed (`.env.*` ignored).
- Record impactful changes in `PROGRESS.md` / `PROGRESS_ZH.md` (architecture, config/env schema, API/WS contracts, infra/docker, key docs).