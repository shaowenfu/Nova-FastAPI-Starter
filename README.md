# 🌟 Nova FastAPI Starter

> A "Quick-Start" Backend Skeleton for AI Applications: JWT, WebSocket, Pluggable LLM, Optional Memory, and One-Click Dockerization.

<p align="left">
  <a href="./README.md">🇺🇸 English</a> | 
  <a href="devDocs/README.zh-CN.md">🇨🇳 中文</a>
</p>

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## 📖 Vision

We are dedicated to providing a **concise, efficient, and production-grade** backend infrastructure for AI startups and individual developers.

- **🚀 Ready to Launch**: No cumbersome configurations; go from zero to API online in minutes.
- **🧩 Pluggable Modularity**: JWT authentication, WebSocket streaming, LLM adapters, vector memory—enable only what you need.
- **🛡️ First Principles & Occam's Razor**: Clear layering, minimal viable defaults, and "fail-fast" error handling, balancing security with maintainability.
- **🤝 Community-Driven**: An open-source skeleton welcoming contributions (PRs/Issues) for more Vector/LLM adapters and practical examples.

---

## ✨ Core Features

- **LLM Agnostic**: A unified `LLMProvider` interface allows you to switch between OpenAI, DeepSeek, Claude, or local LLMs with a single configuration line.
- **Native Memory**: Features a `MemoryAdapter` interface and `docker-compose.memory.yml` for plug-and-play vector database (ChromaDB) support, disabled by default, enabled on demand.
- **Production Architecture**: 
  - **DDD-Lite**: Clear `Router` -> `Service` -> `Repository` layering.
  - **Async First**: Full-stack asynchronous database support (Mongo + MySQL + Redis).
  - **Security**: Built-in JWT (Access/Refresh Token) and WebSocket authentication mechanisms.
- **DevOps Ready**: Includes `Dockerfile` and modular `docker-compose` configurations for easy deployment.

---

## ⚡ Quick Start

### 1. Setup Environment

```bash
git clone https://github.com/your-username/nova-fastapi-starter.git
cd nova-fastapi-starter

# Copy environment variables configuration
cp .env.example .env
```

### 2. Start Service (Minimal Mode)

In default mode, the system relies only on basic components (MySQL/Redis/Mongo) and does not launch the vector database.

```bash
docker-compose up -d --build
```

Access API Documentation: `http://localhost:8000/docs`

### 3. Enable AI Memory (Optional)

If you require RAG (Retrieval-Augmented Generation) or long-term memory capabilities:

1.  Modify `.env` to set `MEMORY_ENABLED=true`.
2.  Start the configuration including the vector database (ChromaDB):

```bash
docker-compose -f docker-compose.yml -f docker-compose.memory.yml up -d
```

---

## 🔌 LLM Configuration Guide

Nova uses a standardized OpenAI-compatible layer, supporting almost all mainstream models. Simply modify your `.env` to switch:

**Using DeepSeek / Moonshot / DashScope:**
```ini
LLM_BASE_URL=https://api.deepseek.com  # Or other compatible endpoints
LLM_API_KEY=sk-your-key-here
LLM_MODEL=deepseek-chat
```

**Using Local LLM (Ollama/vLLM):**
```ini
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=llama3
```

---

## 🛠️ Directory Structure

```text
├── core/               # Core configuration, exception definitions, logging
│   └── memory_adapter/ # [Unique] Memory module adapter (Connector/Normalizer)
├── dependencies/       # FastAPI Dependency Injection (Auth, Permissions)
├── infrastructure/     # Infrastructure layer (DB Clients, Repositories)
├── routers/            # Routing layer (API interface definitions)
├── services/           # Business logic layer (Auth, LLM, Chat, SMS)
└── static/             # Simple test pages (WebSocket Tester, etc.)
```

## 🐛 Debugging (VS Code)

We provide a pre-configured `.vscode/launch.json`.
1. Open the project in VS Code.
2. Select the **Run and Debug** tab.
3. Choose **"Nova: Debug API (Uvicorn)"** and press F5.
   - Requires your Python environment to include `uvicorn` and `fastapi`.

## 🚢 Deployment (GitHub Actions)

A template workflow is included in `.github/workflows/deploy.yml`.
- **Target**: Self-hosted runner (e.g., AWS EC2 with Docker installed).
- **Setup**:
  1. Add a runner with tag `ecs-backend` to your repo.
  2. Create an env file on the runner at `$HOME/backend_env` containing production secrets.
  3. Push to `main` branch to trigger auto-deployment.

---

## 🤝 Contribution

We highly welcome community contributions! Our current Roadmap includes:

- [ ] Adapting more vector databases (Qdrant, Milvus).
- [ ] Adding more streaming output examples for various LLM Providers.
- [ ] Providing frontend demo (React/Vue) integration examples.

Please refer to the [Development Regulations](devDocs/develop_regulations.md) for more details.

## 📚 Documentation

- **Development Regulations**: [English](devDocs/develop_regulations.md) | [中文](devDocs/develop_regulations_zh.md) - Architectural principles, directory responsibilities, and coding standards.
- **Progress Log**: [English](devDocs/PROGRESS.md) | [中文](devDocs/PROGRESS_ZH.md) - Records of architectural changes and major versions.

---

## 📄 License

MIT © 2025 Nova Contributors
