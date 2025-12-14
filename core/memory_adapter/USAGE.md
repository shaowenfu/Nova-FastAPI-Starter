# Memory Adapter 使用指南

该模块是一个可以直接放入 `/core` 的 Mem0 适配器，不需要修改其他目录即可为后端提供记忆读写能力。按照以下步骤集成：

## 1. 安装依赖
运行环境需要包含以下库（版本与现有项目可保持一致）：
- `mem0`
- `langchain-community`
- `dashscope`
- `openai>=1.0.0`
- `python-dotenv`

## 2. 配置环境变量
在 `.env` 或配置中心写入：
```
DEEPSEEK_API_KEY=...
DEEPSEEK_CHAT_MODEL=deepseek-chat
DEEPSEEK_API_BASE=https://api.deepseek.com
DASHSCOPE_API_KEY=... # 推荐使用该变量名；兼容 ALIBABA_API_KEY
DASHSCOPE_EMBED_MODEL=text-embedding-v2
MEM0_USER_ID=123666
MEM0_VECTOR_STORE_PATH=可选自定义路径
MEM0_NORMALIZATION_FILE=可选规则文件路径
```
如果不设置 `MEM0_VECTOR_STORE_PATH`，适配器会默认写入 `core/memory_adapter/storage/persistent_memories_db`。确保该目录可写并在 `.gitignore` 中忽略。

## 3. 应用启动时初始化
在后端启动流程（如 `main.py` 的 lifespan）中调用一次 `init_memory_adapter()`：
```python
from core.memory_adapter import init_memory_adapter

def lifespan(app: FastAPI):
    init_memory_adapter()
    yield
```
该函数会校验必要的环境变量并创建共享的 `Memory` 实例，可安全重复调用。

## 4. 使用公开方法
- `store_memories(messages, user_id=None)`  
  `messages` 为 `{ "role": str, "content": str }` 的列表，空值会被自动过滤。
- `fetch_memories(query, user_id=None, limit=3, context=None)`  
  先执行 `query_normalization`，再返回记忆字符串列表。`context` 可传入 `{"replacements": {"他": "李雷"}}` 这类临时映射。
- `build_memory_block(query, user_id=None, limit=3, header="相关记忆：")`  
  直接返回格式化好的中文记忆块，例如：
  ```
  相关记忆：
  - 用户喜欢早上冥想
  - 最近正在准备考试
  ```
  可直接放入 prompt 的 system 字段或其它上下文。

如果未传 `user_id`，会退回到 `MEM0_USER_ID`，多用户场景请务必传入真实用户 ID。

**多层级命名空间（可选）**  
Mem0 仅提供 `user_id` 维度的隔离。如果需要在“用户”之下再细分（例如按 agent），推荐在业务层拼接命名空间：
```python
def agent_scope(user_id: str, agent_id: str) -> str:
    return f"{user_id}:{agent_id}"

store_memories(messages, user_id=agent_scope(user_id, agent_id))
fetch_memories(query, user_id=agent_scope(user_id, agent_id))
```
这样不同 agent 的记忆互不干扰，同时仍可在需要时遍历该用户的所有 agent 来实现“用户级”聚合。

## 5. 运维提示
- 适配器内部是同步实现，但线程安全。FastAPI 默认在线程池中执行同步函数，不会阻塞事件循环。
- 真正的瓶颈通常是 DashScope/DeepSeek 请求配额，注意监控并定期更换 Key。
- 若后续要拆分成独立服务，直接连同 `.env` 配置一起复制整个 `core/memory_adapter` 目录即可，无需调整其他代码。

### 健康检查（连通性与密钥有效性）
提供脚本 `scripts/healthcheck_dashscope.py` 验证以下内容：
- 环境变量发现：优先 `DASHSCOPE_API_KEY`，兼容 `ALIBABA_API_KEY`。
- 基础网络连通：请求 DashScope 兼容端点。
- 嵌入向量生成：调用 `langchain-community` 的 `DashScopeEmbeddings`。

运行方式：
```
python scripts/healthcheck_dashscope.py
```
脚本会输出结构化结果，失败时以非零退出码终止，便于 CI 集成。

## 6. Query Normalization 规则维护
- 默认规则文件为 `core/memory_adapter/normalization_map.json`，可通过 `MEM0_NORMALIZATION_FILE` 指向自定义路径。
- 文件结构：
  ```json
  {
    "replacements": {
      "AI助手": "陪伴代理A"
    },
    "regex_replacements": [
      {
        "pattern": "\\s+",
        "replacement": " "
      }
    ]
  }
  ```
- 测试或运营人员可以直接编辑该文件新增映射，重启服务后即生效。
- 如需临时扩展（例如根据上下文把“他”替换成当前 agent 名称），在调用 `fetch_memories` 或 `build_memory_block` 时传入 `context={"replacements": {"他": "Agent A"}}` 即可。
- 不熟悉 JSON 写法时，可参考 `core/memory_adapter/NORMALIZATION_GUIDE.md` 获取图文指引。
