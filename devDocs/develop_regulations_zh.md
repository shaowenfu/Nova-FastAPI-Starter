# Nova FastAPI Starter · 开发规范（中文）

核心理念：第一性原理 + 奥卡姆剃刀 + 错误早抛。意图清晰，拒绝隐式魔法，尽早暴露问题。

## 1) 框架总览（树形）
```
nova-fastapi-starter/
├── main.py                # 生命周期、路由聚合、异常处理、静态挂载
├── core/                  # 配置、日志、通用异常、memory 脚手架
├── dependencies/          # 依赖提供者（config/auth/token/LLM/SMS/repo）
├── routers/               # HTTP/WS 控制器（薄）
├── services/              # 业务编排；基础在 services/basic
├── infrastructure/        # db 客户端、模型、仓库
├── static/                # auth 指南、WS 调试、通知、导航
└── scripts/               # 可选脚本
```

## 2) 职责与边界
| 模块 | 责任 | 要做 | 禁止 | 依赖 |
| --- | --- | --- | --- | --- |
| `main.py` | 生命周期、路由聚合、异常、静态 | 启停 DB/memory/WS；注册路由/异常 | 业务逻辑；临时创建客户端 | core, routers, infra/db, services/basic/websocket |
| `core/` | 配置、日志、通用异常、memory 占位 | 校验配置，提供 logger | 业务/数据访问 | stdlib |
| `dependencies/` | 依赖提供 | 提供 config、ModelService、auth/token/SMS、仓库 | 在路由里 new 服务/客户端 | core, services/basic, infra/repos |
| `routers/` | HTTP/WS 控制器 | 校验、`Depends`、返回 DTO | 写业务、直连 DB/LLM | dependencies, services/basic, infra/models |
| `services/basic/` | auth/llm/sms/websocket 编排 | 抛 `BaseAPIException` 派生类，协调 repo/LLM/memory | 用 `HTTPException`；new 客户端 | core, infra/repos, infra/db |
| `infra/db/` | 客户端单例 | `connect_*`/`close_*`/`get_*` | 执行查询 | core/config |
| `infra/repos/` | CRUD 数据访问 | 返回 Pydantic 模型（`DB*`/`*Create`/`*Response`） | 业务逻辑、记录秘钥 | infra/db, infra/models |
| `infra/models/` | 数据契约 | Pydantic 模型、序列化 | 跨层逻辑 | stdlib |
| `static/` | 静态演示页 | 独立 HTML | 后端耦合 | 无 |

## 3) 启动与依赖
- 启动：日志 → connect mongo/mysql/redis → init memory → init WebSocketService → 进入服务。
- 关闭：清理 WebSocketService → 关闭 mongo/redis/mysql → 关闭 `ModelService`。
- 单例：DB 客户端、`ModelService`、`WebSocketService` 只在 lifespan 初始化一次。
- 依赖全部来自 `dependencies/providers.py`，禁止路由/服务内手动实例化。

## 4) 编码规范
- Python 3.11，4 空格，类型标注齐全，函数精简。
- 日志：`core.logger.get_logger`；禁止模块内重配日志。
- 错误：缺必需配置直接抛；服务层用 `BaseAPIException`，不用 `HTTPException`；不做静默降级。
- 注释克制，只补充意图/边界。

## 5) 认证与安全
- 仅 JWT：HTTP/WS 用户 ID 仅来自 token `sub`，禁止 header/query 透传。
- WS token 通过首个 `Sec-WebSocket-Protocol` 传递并回显；HTTP 用 `Authorization: Bearer <token>` 或 `X-Auth-Token`。
- 秘钥放 `.env`（源自 `.env.example`），绝不提交真实秘钥。

## 6) WebSocket
- 端点 `/ws/chat`；管理+handler 在 `services/basic/websocket.py`。
- 内置 `ping/status/echo/llm_stream`；启动时可 `register_handler("type", handler)` 扩展。
- `UnifiedWebSocketRequest`：必填 `type`，可选 `agent_id/message/payload/context`；大小/超时由 `core/config.py` 控制。
- 错误早抛：非法/超限直接报错或关闭，可返回结构化 error payload，无兜底。

## 7) LLM
- OpenAI 兼容入口 `services/basic/llm.py`，由 `DEFAULT_MODEL_PROVIDER` + 通用 `LLM_` 配置驱动。
- 所有调用必须 `await`；只捕获并透传 `LLMServiceError`；不要用线程池包裹异步客户端。

## 8) Memory（原生向量支持）
- `core/memory_adapter` 提供可插拔的持久化接口。
- 默认：**ChromaDB**，通过 `docker-compose.memory.yml` 启动。
- 使用：设置 `MEMORY_ENABLED=true`。仅使用 `store_memories` 和 `fetch_memories` 接口。
- 禁止将业务逻辑与特定向量库强耦合，使用 Adapter 模式。

## 9) 数据访问
- 只用单例连接：`get_mysql_session`、`get_redis_client`、Mongo helpers；禁止自建连接。
- 仓库只做 CRUD，不记录秘钥，不改全局状态；业务编排在服务层。

## 10) 配置
- 链路：`.env`（来自 `.env.example`）→ docker-compose env_file → `core/config.py`。
- **通用 Key**：使用 `LLM_BASE_URL`, `SMS_ACCESS_KEY_ID`。禁止核心配置中出现特定厂商前缀（如 `ALI_SMS`, `DEEPSEEK`）。
- 内网用服务名（redis/mysql/mongo/chroma）；必需项（如 JWT 秘钥）缺失必须报错。

## 11) 运行
- 本地：确保 Redis/Mongo/MySQL（以及 Chroma 如启用）运行，执行 `python -m uvicorn main:app --reload`。
- Compose：`docker compose up --build`。需 RAG 支持请追加 `-f docker-compose.memory.yml`。
- 运维：Adminer/Redis Commander 可通过 `--profile ops` 开启。

## 12) 测试与质量
- pytest + pytest-asyncio；每个特性至少 1 成功 + 1 失败用例。
- 优先依赖覆盖/假实现，避免直连外部；不只测 happy path。
- 遵循 PEP8，导入有序，移除未用依赖。

## 13) 提交与文档
- 使用 Conventional Commits（如 `feat(auth): ...`，`fix(ws): ...`），小步提交。
- 新增/删除模块需同步更新文档/静态页。
- `.env`、真实秘钥一律不提交（`.env.*` 已忽略）。
- 关键变更需在 `PROGRESS.md` / `PROGRESS_ZH.md` 记录（架构、配置/环境变量、API/WS 契约、基础设施/容器、重要文档）。