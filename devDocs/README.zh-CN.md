# 🌟 Nova FastAPI Starter

> **为 AI 应用打造的“快启快飞”后端骨架**
>
> A "Quick-Start" Backend Skeleton for AI Applications: JWT, WebSocket, Pluggable LLM, Optional Memory, and One-Click Dockerization.

<p align="left">
  <a href="../README.md">🇺🇸 English</a> | 
  <a href="./README.zh-CN.md">🇨🇳 中文</a>
</p>

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## 📖 愿景 (Vision)

我们致力于为 AI 初创公司和个人开发者提供一套**简洁、高效、生产级**的后端基础设施。

- **🚀 快启快飞 (Ready to Launch)**: 拒绝繁琐的配置，从零到 API 上线只需几分钟。
- **🧩 模块化 (Pluggable)**: JWT 鉴权、WS 流式通信、LLM 适配器、向量记忆——需要什么，开启什么。
- **🛡️ 第一性原理 (First Principles)**: 坚持奥卡姆剃刀原则。分层清晰，默认最小化运行，错误早抛（Fail Fast），兼顾安全与可维护性。
- **🤝 社区共建 (Community)**: 这是一个开放的骨架，欢迎共建更多 Vector/LLM 适配器和实战示例。

---

## ✨ 核心特性 (Features)

- **LLM Agnostic (模型无关)**: 统一的 `LLMProvider` 接口，一行配置切换 OpenAI, DeepSeek, Claude 或 Local LLM。
- **Native Memory (原生记忆)**: 基于 **[Mem0](https://github.com/mem0ai/mem0)** 构建，提供即插即用的向量库（ChromaDB）支持，默认关闭，按需开启。
- **Production Architecture**: 
  - **DDD-Lite**: 清晰的 `Router` -> `Service` -> `Repository` 分层。
  - **Async First**: 全链路异步数据库支持 (Mongo + MySQL + Redis)。
  - **Security**: 内置 JWT (Access/Refresh Token) 与 WebSocket 鉴权机制。
- **DevOps Ready**: 包含 `Dockerfile` 与模块化 `docker-compose` 配置。

---

## ⚡ 快速开始 (Quick Start)

### 1. 环境准备

```bash
git clone https://github.com/your-username/nova-fastapi-starter.git
cd nova-fastapi-starter

# 复制环境变量配置
cp .env.example .env
```

### 2. 启动服务 (最小化模式)

默认模式下，系统仅依赖 MySQL/Redis/Mongo 基础组件，不启动向量库。

```bash
docker-compose up -d --build
```

访问文档: `http://localhost:8000/docs`

### 3. 开启 AI 记忆 (Optional)

如果你需要 RAG (检索增强生成) 或长期记忆功能：

1. 修改 `.env` 设置 `MEMORY_ENABLED=true`。
2. 启动包含向量库 (ChromaDB) 的配置：

```bash
docker-compose -f docker-compose.yml -f docker-compose.memory.yml up -d
```

---

## 🔌 LLM 配置指南

Nova 采用了标准化的 OpenAI 兼容层，支持几乎所有主流模型。修改 `.env` 即可切换：

**使用 DeepSeek / Moonshot / DashScope:**
```ini
LLM_BASE_URL=https://api.deepseek.com  # 或其他兼容接口
LLM_API_KEY=sk-your-key-here
LLM_MODEL=deepseek-chat
```

**使用 Local LLM (Ollama/vLLM):**
```ini
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=llama3
```

---

## 🛠️ 目录结构 (Structure)

```text
├── core/               # 核心配置、异常定义、日志
│   └── memory_adapter/ # [Unique] 基于 Mem0 的适配器 (Connector/Normalizer)
├── dependencies/       # FastAPI 依赖注入 (Auth, Permissions)
├── infrastructure/     # 基础设施层 (DB Clients, Repositories)
├── routers/            # 路由层 (API 接口定义)
├── services/           # 业务逻辑层 (Auth, LLM, Chat, SMS)
└── static/             # 简单的测试页面 (WebSocket Tester 等)
```

## 🐛 调试指南 (VS Code)

项目已内置 `.vscode/launch.json` 调试配置。
1. 在 VS Code 中打开项目。
2. 切换到 **运行和调试 (Run and Debug)** 侧边栏。
3. 选择 **"Nova: Debug API (Uvicorn)"** 并按 F5 启动。
   - 请确保当前 Python 环境已安装 `uvicorn` 和 `fastapi`。

## 🚢 部署指南 (GitHub Actions)

我们提供了一个标准的 CI/CD 模板 `.github/workflows/deploy.yml`。
- **适用场景**: 自托管 Runner (如安装了 Docker 的 AWS EC2/阿里云 ECS)。
- **配置步骤**:
  1. 在 GitHub 仓库添加一个 Tag 为 `ecs-backend` 的 Runner。
  2. 在服务器 `$HOME/backend_env` 路径下创建生产环境配置文件（包含真实秘钥）。
  3. 推送代码到 `main` 分支即可触发自动部署。

---

## 🤝 参与贡献 (Contribution)

我们非常欢迎社区贡献！目前的 Roadmap 包括：

- [ ] 适配更多向量数据库 (Qdrant, Milvus)。
- [ ] 增加更多 LLM Provider 的流式输出示例。
- [ ] 提供前端 Demo (React/Vue) 对接示例。

请阅读 [开发规范 (Develop Regulations)](develop_regulations_zh.md) 了解更多细节。

## 📚 文档索引 (Documentation)

- **开发规范 (Regulations)**: [English](develop_regulations.md) | [中文](develop_regulations_zh.md) - 架构原则、目录职责与编码标准。
- **更新日志 (Progress)**: [English](PROGRESS.md) | [中文](PROGRESS_ZH.md) - 架构变更与重大版本记录。

---

## 🙏 致谢 (Acknowledgements)

Nova 站在巨人的肩膀上。特别感谢以下开源项目：

- [FastAPI](https://fastapi.tiangolo.com/): 现代、高性能的 Web 框架。
- [Mem0](https://github.com/mem0ai/mem0): 我们记忆模块的核心基座。
- [ChromaDB](https://www.trychroma.com/): 强大的向量存储后端。
- [SQLAlchemy](https://www.sqlalchemy.org/): 稳健的异步 ORM 基础。

## 📄 License

MIT © 2025 Nova Contributors
