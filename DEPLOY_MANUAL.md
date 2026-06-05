# Mem0 自托管部署手册

> 部署日期：2026-05-29 | 仓库：`~/mem0` | 基于 [mem0ai/mem0](https://github.com/mem0ai/mem0) main 分支

---

## 1. 服务架构

```
┌──────────────────────────────────────────────────────────┐
│                    局域网 192.168.24.0/24                  │
│                                                          │
│  浏览器 ──HTTP──► Dashboard :3000 ──► API :8888           │
│                          │                  │             │
│                     Next.js 15          FastAPI           │
│                          │                  │             │
│                          └──── 内网 ────► PgVector :5432  │
│                                    PostgreSQL + pgvector   │
│                                            │              │
│                          ┌─────────────────┼──────────┐   │
│                          │                 │          │   │
│                     DeepSeek API    硅基流动 API        │   │
│                   (LLM deepseek-chat)  (Embedding       │   │
│                                         Pro/BAAI/bge-m3) │   │
│                                          1024 维          │   │
└──────────────────────────────────────────────────────────┘
```

| 服务 | 容器名 | 镜像 | 主机端口 | 容器端口 |
|------|--------|------|---------|---------|
| API | `mem0-dev-mem0-1` | `mem0-dev-mem0` (自建) | **8888** | 8000 |
| PostgreSQL | `mem0-dev-postgres-1` | `ankane/pgvector:v0.5.1` | **8432**（仅 localhost） | 5432 |
| Dashboard | `mem0-dev-mem0-dashboard-1` | `mem0-dev-mem0-dashboard` (自建) | **3000** | 3000 |

---

## 2. 访问地址

| 服务 | 本机 | 局域网 |
|------|------|--------|
| Dashboard | http://localhost:3000 | http://192.168.24.130:3000 |
| API | http://localhost:8888 | http://192.168.24.130:8888 |
| API 文档 | http://localhost:8888/docs | http://192.168.24.130:8888/docs |
| OpenAPI JSON | http://localhost:8888/openapi.json | http://192.168.24.130:8888/openapi.json |

> **注意：** Dashboard 和 API 的 URL 现在通过环境变量配置（见第 4 节 `.env` 示例）。默认值为 `localhost`，局域网访问时需要在 `.env` 中设置 `DASHBOARD_URL` 和 `NEXT_PUBLIC_API_URL` 为局域网 IP（如 `http://192.168.24.130:3000`），否则 Dashboard 无法正确回调 API。

---

## 3. 配置详情

### 3.1 LLM — DeepSeek

| 参数 | 值 |
|------|-----|
| Provider | `openai`（OpenAI 兼容模式） |
| Model | `deepseek-chat` |
| Base URL | `https://api.deepseek.com` |
| API Key | 存储在数据库 `settings` 表中 |
| Temperature | 0.2 |

### 3.2 Embedding — 硅基流动（SiliconFlow）

| 参数 | 值 |
|------|-----|
| Provider | `openai`（OpenAI 兼容模式） |
| Model | `Pro/BAAI/bge-m3` |
| Base URL | `https://api.siliconflow.cn/v1` |
| API Key | 存储在数据库 `settings` 表中 |
| Dimensions | 1024 |

### 3.3 向量存储 — pgvector

| 参数 | 值 |
|------|-----|
| Provider | `pgvector` |
| Host | `postgres`（容器内网络） |
| Port | 5432 |
| Database | `postgres` |
| User / Password | `postgres` / `postgres` |
| Collection | `memories` |
| embedding_model_dims | 1024 |

### 3.4 认证

| 参数 | 值 |
|------|-----|
| AUTH_DISABLED | `true`（本地开发模式，所有端点开放） |
| JWT_SECRET | `mem0-local-dev-secret-2024` |
| MEM0_TELEMETRY | `false` |

> ⚠️ `AUTH_DISABLED=true` 仅用于本地开发。生产环境请创建 admin 账号并关闭此选项。

### 3.5 网络与 CORS

跨域资源共享（CORS）配置直接影响局域网内客户端能否正常调用 API。

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `DASHBOARD_URL` | `http://localhost:3000` | Dashboard 地址，自动加入 CORS 允许列表 |
| `EXTRA_CORS_ORIGINS` | （空） | 额外的 CORS 允许来源，逗号分隔 |

**CORS 行为：**

- **`AUTH_DISABLED=true` 时（当前配置）：** CORS 自动允许所有来源（`*`），局域网内任何客户端可直接调用 API，无需逐个配置来源。这对于多设备 LAN 接入非常方便。
- **认证启用时（`AUTH_DISABLED=false`）：** 只有 `DASHBOARD_URL` + `EXTRA_CORS_ORIGINS` 中列出的来源被允许。需要在 `EXTRA_CORS_ORIGINS` 中添加局域网客户端的地址。

**示例（认证启用时添加 LAN 来源）：**
```env
EXTRA_CORS_ORIGINS=http://192.168.24.50:8080,http://192.168.24.60:3001
```

---

## 4. 环境文件

### `~/mem0/server/.env`

```env
AUTH_DISABLED=true
MEM0_TELEMETRY=false
JWT_SECRET=mem0-local-dev-secret-2024
OPENAI_API_KEY=sk-placeholder
MEM0_DEFAULT_LLM_MODEL=deepseek-chat

# ── 局域网访问配置（设置为实际 LAN IP 以支持局域网设备访问）──
DASHBOARD_URL=http://192.168.24.130:3000
NEXT_PUBLIC_API_URL=http://192.168.24.130:8888
INSTANCE_NAME=Mem0

# ── CORS 扩展（可选，AUTH_DISABLED=true 时无需配置）──
# EXTRA_CORS_ORIGINS=http://192.168.24.50:8080,http://192.168.24.60:3001
```

> `OPENAI_API_KEY=sk-placeholder` 仅用于服务启动初始化。真实的 LLM 和 Embedding API Key 通过 `POST /configure` 注入，持久化在 PostgreSQL 数据库中。
>
> **局域网部署注意：** 如果局域网设备需要访问 Dashboard 和 API，请将 `DASHBOARD_URL` 和 `NEXT_PUBLIC_API_URL` 设置为服务器的局域网 IP 地址（如上例）。若仅本机使用，可保持 `localhost` 不变。

---

## 5. API 使用指南

### 5.1 配置管理

```bash
# 查看当前配置
curl http://192.168.24.130:8888/configure

# 更新 LLM 配置
curl -X POST http://192.168.24.130:8888/configure \
  -H "Content-Type: application/json" \
  -d '{
    "llm": {
      "provider": "openai",
      "config": {
        "model": "deepseek-chat",
        "api_key": "sk-xxx",
        "openai_base_url": "https://api.deepseek.com",
        "temperature": 0.2
      }
    }
  }'

# 更新 Embedding 配置
curl -X POST http://192.168.24.130:8888/configure \
  -H "Content-Type: application/json" \
  -d '{
    "embedder": {
      "provider": "openai",
      "config": {
        "model": "Pro/BAAI/bge-m3",
        "api_key": "sk-xxx",
        "openai_base_url": "https://api.siliconflow.cn/v1",
        "embedding_dims": 1024
      }
    },
    "vector_store": {
      "provider": "pgvector",
      "config": {
        "embedding_model_dims": 1024
      }
    }
  }'
```

> **重要：** 更改 Embedding 模型或维度后，必须执行 `POST /reset` 重建向量表，否则维度不匹配会导致插入失败。

### 5.2 记忆操作

```bash
# 添加记忆
curl -X POST http://192.168.24.130:8888/memories \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "用户偏好和事实描述"}],
    "user_id": "alice"
  }'

# 搜索记忆（指定用户）
curl -X POST http://192.168.24.130:8888/search \
  -H "Content-Type: application/json" \
  -d '{"query": "搜索关键词", "user_id": "alice"}'

# 搜索记忆（跨所有用户 —— 不传 filters 即可搜索全部）
curl -X POST http://192.168.24.130:8888/search \
  -H "Content-Type: application/json" \
  -d '{"query": "搜索关键词"}'

# 搜索记忆（使用 filters 对象）
curl -X POST http://192.168.24.130:8888/search \
  -H "Content-Type: application/json" \
  -d '{"query": "搜索关键词", "filters": {"user_id": "alice"}}'

# 获取所有记忆
curl http://192.168.24.130:8888/memories?user_id=alice

# 获取单条记忆
curl http://192.168.24.130:8888/memories/{memory_id}

# 更新记忆
curl -X PUT http://192.168.24.130:8888/memories/{memory_id} \
  -H "Content-Type: application/json" \
  -d '{"text": "更新后的内容"}'

# 删除单条记忆
curl -X DELETE http://192.168.24.130:8888/memories/{memory_id}

# 删除用户所有记忆
curl -X DELETE "http://192.168.24.130:8888/memories?user_id=alice"

# 重置所有记忆（清空向量表并重建）
curl -X POST http://192.168.24.130:8888/reset
```

> **搜索 filters 说明：** `POST /search` 的 `filters` 参数现在是**可选的**。省略 `filters` 将搜索所有用户的记忆，适合局域网内全局搜索场景。也可以使用请求体顶层的 `user_id`、`agent_id`、`run_id`（已标记为 deprecated，仍可用，建议迁移到 `filters` 对象）。

### 5.3 API Key 管理（启用认证后）

```bash
# 查看已打包的 Provider
curl http://192.168.24.130:8888/configure/providers
# 返回: {"llm": ["openai", "anthropic", "gemini"], "embedder": ["openai", "gemini"]}
```

---

## 6. Docker 管理命令

```bash
cd ~/mem0/server

# ── 生命周期 ──
docker compose up -d              # 启动所有服务
docker compose up -d --build      # 重新构建并启动
docker compose down               # 停止服务（保留数据卷）
docker compose down -v            # 停止并删除数据卷（清空所有数据）
docker compose restart mem0       # 重启 API 服务
docker compose ps                 # 查看容器状态

# ── 日志 ──
docker compose logs -f            # 跟踪所有服务日志
docker compose logs -f mem0       # 仅跟踪 API 日志
docker compose logs --tail=50 mem0  # 最近 50 行 API 日志

# ── 调试 ──
docker compose exec -T postgres psql -U postgres   # 进入 PostgreSQL
docker compose exec -T postgres psql -U postgres -c "\d memories"  # 查看表结构
docker compose exec -T postgres psql -U postgres -d mem0_app -c "SELECT value FROM settings WHERE key='config_overrides';"  # 查看持久化配置
```

> **PostgreSQL 端口安全说明：** PostgreSQL 端口现在绑定到 `127.0.0.1:8432:5432`（仅本机可访问），防止局域网内其他设备直接连接数据库。如果需要从局域网其他设备访问 PostgreSQL（如使用 pgAdmin 等工具），需将 `docker-compose.yaml` 中的端口绑定改为 `8432:5432`（去掉 `127.0.0.1` 前缀）。

---

## 7. 目录结构（部署相关）

```
~/mem0/
├── server/
│   ├── .env                          # 环境变量（API Key 占位、认证、遥测、CORS）
│   ├── docker-compose.yaml           # Docker Compose 编排（可配置 URL、CORS、本地源码安装）
│   ├── Dockerfile                    # API 生产镜像
│   ├── dev.Dockerfile                # API 开发镜像（当前使用）
│   ├── main.py                       # FastAPI 主程序（含重试机制、智能 CORS、404 处理）
│   ├── server_state.py               # 配置管理与持久化
│   ├── init-db.sh                    # PostgreSQL 初始化脚本
│   ├── requirements.txt              # Python 依赖
│   ├── alembic/                      # 数据库迁移
│   ├── dashboard/                    # Dashboard 前端
│   │   ├── Dockerfile                # 已修改：node:22 + pnpm@9
│   │   ├── entrypoint.sh             # 运行时环境变量替换
│   │   └── src/
│   │       ├── middleware.ts          # 认证中间件（cookie 检查）
│   │       ├── lib/auth.tsx           # 前端认证逻辑
│   │       └── app/api/auth/refresh/  # Cookie 管理（已修改 secure 逻辑）
│   └── scripts/                      # 管理脚本
├── mem0/                             # Python SDK 核心库
│   ├── llms/openai.py                # OpenAI LLM（支持 openai_base_url）
│   ├── embeddings/openai.py          # OpenAI Embedding（支持 openai_base_url）
│   ├── vector_stores/pgvector.py     # pgvector 向量存储
│   └── memory/main.py                # 核心记忆逻辑（已修改：允许空 filters 全局搜索）
└── docker-compose.yaml               # 根目录 compose（未使用）
```

---

## 8. 已修改文件清单

### 初始部署修改（commit `68dc60be`）

| 文件 | 修改内容 | 原因 |
|------|---------|------|
| `server/docker-compose.yaml` | `DASHBOARD_URL` 和 `NEXT_PUBLIC_API_URL` 改为 `192.168.24.130` | 支持局域网访问 |
| `server/dashboard/Dockerfile` | `node:20-alpine` → `node:22-alpine` | pnpm 11 要求 Node 22+ |
| `server/dashboard/Dockerfile` | `corepack enable pnpm` → `npm install -g pnpm@9` | pnpm 11 的 build script 审批机制导致安装失败 |
| `server/dashboard/src/app/api/auth/refresh/route.ts` | `secure: process.env.NODE_ENV === "production"` → `secure: process.env.COOKIE_SECURE === "true"` | Docker 内 `NODE_ENV=production` 导致 cookie `secure=true`，HTTP 下浏览器不发送 cookie |

### 后续迭代修改

| 文件 | 修改内容 | 原因 |
|------|---------|------|
| `server/docker-compose.yaml` | `DASHBOARD_URL` / `NEXT_PUBLIC_API_URL` / `INSTANCE_NAME` 改为通过 `${ENV:-default}` 环境变量配置（不再硬编码 IP） | 支持灵活部署，适配不同网络环境 |
| `server/docker-compose.yaml` | 新增 `EXTRA_CORS_ORIGINS` 环境变量 | 允许管理员添加额外的 CORS 来源 |
| `server/docker-compose.yaml` | PostgreSQL 端口绑定改为 `127.0.0.1:8432:5432`（仅 localhost） | 安全加固，防止局域网直连数据库 |
| `server/docker-compose.yaml` | 新增 `..:/opt/mem0-src` 卷挂载，启动命令改为 `pip install /opt/mem0-src` | 从本地源码安装 mem0，方便开发调试 |
| `server/docker-compose.yaml` | Dashboard 健康检查从 `localhost` 改为 `127.0.0.1` | 避免某些环境下 localhost 解析问题 |
| `server/main.py` | 新增 `_retry_upstream` 装饰器，对 `POST /memories` 和 `POST /search` 自动重试瞬时上游错误（最多 3 次，线性退避） | 提高上游 API 超时/限流时的请求成功率 |
| `server/main.py` | CORS 智能配置：`AUTH_DISABLED=true` 时自动允许所有来源（`*`） | 局域网多设备免配置接入 |
| `server/main.py` | `EXTRA_CORS_ORIGINS` 环境变量支持，逗号分隔的额外 CORS 来源 | 认证模式下灵活添加允许的客户端来源 |
| `server/main.py` | `DELETE /memories/{id}` 返回正确的 404（无效 ID / 未找到记忆） | 之前返回通用错误，现在区分"不存在"和"服务器错误" |
| `server/main.py` | `POST /search` 兼容请求体顶层 `user_id`/`agent_id`/`run_id`（标记 deprecated，自动合并到 filters） | 向后兼容旧版客户端调用方式 |
| `mem0/memory/main.py` | `Memory.get_all()` 和 `Memory.search()`（含异步版本）不再强制要求 filters 包含 user_id/agent_id/run_id | 允许空 filters 搜索所有用户的记忆，支持局域网全局搜索场景 |

---

## 9. 故障排查

### 9.1 Dashboard 登录后不跳转

**症状：** 输入账号密码登录成功，但页面不跳转到主界面。

**原因：** Cookie `secure=true` 但通过 HTTP 访问，浏览器拒绝发送。

**排查：**
```bash
# 检查 cookie secure 设置
grep -n "secure" ~/mem0/server/dashboard/src/app/api/auth/refresh/route.ts
# 应为: secure: process.env.COOKIE_SECURE === "true"
```

**修复：** 已在 commit `68dc60be` 中修复。清除浏览器 cookie 后重试。

### 9.2 记忆添加成功但搜索无结果

**症状：** `POST /memories` 返回 200，但 `GET /memories` 和 `POST /search` 返回空。

**原因：** pgvector 表维度与 Embedding 模型输出维度不匹配。

**排查：**
```bash
cd ~/mem0/server
# 查看表维度
docker compose exec -T postgres psql -U postgres -c "\d memories" | grep vector
# 查看日志
docker compose logs mem0 --tail=20 | grep "dimensions"
```

**修复：**
```bash
# 1. 设置正确的维度
curl -X POST http://localhost:8888/configure \
  -H "Content-Type: application/json" \
  -d '{"vector_store":{"provider":"pgvector","config":{"embedding_model_dims":1024}}}'

# 2. 重置（删表重建）
curl -X POST http://localhost:8888/reset
```

### 9.3 LLM/Embedding 502 错误

**症状：** API 返回 `502 Bad Gateway`，日志显示 `401 Unauthorized` 或 `AuthenticationError`。

**原因：** API Key 无效、过期或余额不足。

**排查：**
```bash
docker compose logs mem0 --tail=30 | grep -i "error\|401\|auth"
```

**修复：** 通过 `POST /configure` 重新设置有效的 API Key。

### 9.4 Docker 构建失败

**症状：** `docker compose up -d --build` 失败。

| 错误信息 | 原因 | 修复 |
|---------|------|------|
| `pnpm requires at least Node.js v22` | Node 版本过低 | Dockerfile 改 `node:22-alpine` |
| `ERR_PNPM_IGNORED_BUILDS` | pnpm 11 安全策略 | 改用 `npm install -g pnpm@9` |
| `permission denied` Docker socket | 用户无 Docker 权限 | `sudo usermod -aG docker $USER` |

### 9.5 上游 API 超时/限流

**症状：** `POST /memories` 或 `POST /search` 返回 502 错误，日志显示上游提供商超时或限流。但请求可能在几次重试后成功。

**原因：** DeepSeek / 硅基流动等外部 LLM/Embedding API 出现瞬时故障（超时、限流、服务不可用）。

**自动重试机制：**

`POST /memories` 和 `POST /search` 端点已内置自动重试装饰器 `_retry_upstream`，遇到以下瞬时错误码时会自动重试：

| 错误码 | 含义 | 触发场景 |
|-------|------|---------|
| `provider_timeout` | 提供商响应超时 | LLM/Embedding API 响应慢或网络波动 |
| `provider_rate_limited` | 提供商限流 | API 调用频率过高，触发 429 |
| `provider_unavailable` | 提供商不可用 | API 服务暂时宕机或维护 |
| `datastore_unavailable` | 数据存储不可用 | 向量数据库连接异常 |
| `vector_store_unavailable` | 向量存储不可用 | pgvector 连接异常 |
| `provider_bad_request` | 提供商临时 400 错误 | 上游 API 在故障期间偶发返回 400 |

**重试策略：**
- 最多 **3 次尝试**（1 次初始调用 + 最多 2 次重试）
- 线性退避：第 1 次重试前等待 1 秒，第 2 次重试前等待 2 秒
- 不会重试客户端错误（400/401/403/404/422 等非瞬时错误）

**排查：**
```bash
# 查看重试日志
docker compose logs mem0 --tail=50 | grep "Retrying\|transient"
```

**如果仍然失败：**
1. 检查外部 API 的服务状态和余额
2. 通过 `POST /configure` 切换到备用 API Key 或其他提供商
3. 降低并发请求频率

---

## 10. 配置更新流程

配置通过 `POST /configure` API 注入，采用**递归合并**策略（`_merge_config`），只传需要覆盖的字段即可。配置持久化在 PostgreSQL 的 `settings` 表（`key=config_overrides`），`docker compose down` 不丢失，`docker compose down -v` 才清除。

```
启动流程:
  main.py DEFAULT_CONFIG ──► _load_overrides() 从 DB ──► _merge_config() ──► Memory.from_config()

更新流程:
  POST /configure ──► update_config() ──► _merge_config() ──► Memory.from_config()
                                    └──► _save_overrides() 写入 DB
```

> **注意：** 修改 Embedding 模型或维度后，必须执行 `POST /reset` 重建向量表。

---

## 11. 生产环境建议

如果将此部署用于生产环境，请进行以下调整：

1. **启用认证**
   ```env
   # .env
   AUTH_DISABLED=false
   JWT_SECRET=$(openssl rand -base64 48)
   ```
   然后通过 Dashboard 或 `make bootstrap` 创建 admin 账号。

2. **配置 HTTPS**
   - 使用 Nginx/Caddy 反向代理 + Let's Encrypt 证书
   - 设置环境变量 `COOKIE_SECURE=true`

3. **更换默认密码**
   - PostgreSQL 密码：修改 `docker-compose.yaml` 中的 `POSTGRES_PASSWORD`
   - JWT Secret：生成随机字符串

4. **数据备份**
   ```bash
   docker compose exec -T postgres pg_dump -U postgres postgres > backup.sql
   docker compose exec -T postgres pg_dump -U postgres mem0_app > backup_app.sql
   ```

5. **日志管理**
   ```bash
   # 定期清理请求日志（默认保留 30 天）
   cd ~/mem0/server && make prune-logs
   make prune-logs REQUEST_LOG_RETENTION_DAYS=7
   ```

---

## 12. 外部 Agent 接入指南

外部 Agent 可通过以下 **5 种方式** 接入自托管 mem0 服务：

### 12.1 认证说明

当前 `.env` 设置 `AUTH_DISABLED=true`，所有请求无需认证头。同时，CORS 自动允许所有来源（`*`），因此**局域网内的浏览器端 Agent（如前端应用）可以直接调用 API，无需额外配置 CORS**。

启用认证后（生产环境），支持三种认证方式：

| 方式 | Header 格式 | 适用场景 |
|------|-----------|---------|
| JWT Bearer | `Authorization: Bearer <jwt_token>` | Dashboard 登录后获取 |
| API Key | `X-API-Key: m0sk_xxxxxxxx` | Agent / 程序化调用 |
| Admin Key | `X-API-Key: <ADMIN_API_KEY>` | 管理员全局操作 |

> ⚠️ Python/TypeScript SDK 的 `MemoryClient` 使用 `Authorization: Token xxx` 格式，与自托管服务器的 `Bearer` 格式**不兼容**。接入自托管请用下方 **REST API** 或 **httpx 直接调用**方式。

> 💡 **局域网浏览器端接入：** 当 `AUTH_DISABLED=true` 时，CORS 已自动配置为允许所有来源。这意味着局域网内任何设备上的 Web 应用可以直接通过 `fetch()` 调用 `http://192.168.24.130:8888`，不会被浏览器 CORS 策略拦截。无需在 Nginx 反向代理中额外配置 `Access-Control-Allow-Origin`。

### 12.2 方式一：REST API（推荐，最通用）

任何能发 HTTP 请求的 Agent 都可直接调用。

**Base URL：** `http://192.168.24.130:8888`

#### 认证（启用后）

```bash
# 方式 A: X-API-Key
curl -H "X-API-Key: m0sk_xxxxxxxx" ...

# 方式 B: Bearer JWT（通过 /auth/login 获取）
curl -H "Authorization: Bearer eyJ..." ...
```

#### 添加记忆

```bash
curl -X POST http://192.168.24.130:8888/memories \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "我喜欢在周末去爬山"}
    ],
    "user_id": "agent-user-001",
    "metadata": {"source": "chat-bot"}
  }'
```

**响应示例：**
```json
{
  "results": [
    {
      "id": "b81ce803-...",
      "memory": "User enjoys hiking on weekends.",
      "event": "ADD"
    }
  ]
}
```

#### 搜索记忆

```bash
# 搜索指定用户的记忆
curl -X POST http://192.168.24.130:8888/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "周末活动偏好",
    "user_id": "agent-user-001",
    "top_k": 5
  }'

# 搜索所有用户的记忆（不传 filters，全局搜索）
curl -X POST http://192.168.24.130:8888/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "周末活动偏好",
    "top_k": 10
  }'
```

#### 获取所有记忆

```bash
curl http://192.168.24.130:8888/memories?user_id=agent-user-001
```

#### 删除记忆

```bash
# 删除单条
curl -X DELETE http://192.168.24.130:8888/memories/{memory_id}

# 删除用户所有记忆
curl -X DELETE "http://192.168.24.130:8888/memories?user_id=agent-user-001"
```

#### 完整 API 端点列表

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/docs` | OpenAPI 交互式文档 |
| `POST` | `/memories` | 添加记忆 |
| `GET` | `/memories` | 获取记忆列表 |
| `GET` | `/memories/{id}` | 获取单条记忆 |
| `PUT` | `/memories/{id}` | 更新记忆 |
| `DELETE` | `/memories/{id}` | 删除单条记忆 |
| `DELETE` | `/memories` | 删除用户所有记忆 |
| `GET` | `/memories/{id}/history` | 获取记忆变更历史 |
| `POST` | `/search` | 语义搜索 |
| `POST` | `/reset` | 重置所有记忆 |
| `GET` | `/configure` | 获取当前配置 |
| `POST` | `/configure` | 更新配置 |
| `GET` | `/configure/providers` | 查看已打包 Provider |
| `POST` | `/generate-instructions` | 根据用例生成自定义指令 |
| `GET` | `/entities` | 列出所有实体 |
| `DELETE` | `/entities/{type}/{id}` | 删除实体及关联记忆 |
| `GET` | `/requests` | 查看请求日志 |
| `GET` | `/api-keys` | 管理 API Key |
| `POST` | `/api-keys` | 创建 API Key |
| `DELETE` | `/api-keys/{id}` | 吊销 API Key |
| `POST` | `/auth/login` | 登录 |
| `POST` | `/auth/register` | 注册 |
| `POST` | `/auth/refresh` | 刷新 Token |
| `GET` | `/auth/me` | 获取当前用户 |
| `POST` | `/auth/change-password` | 修改密码 |

### 12.3 方式二：Python 直接调用（httpx/requests）

适用于 Python Agent，直接用 HTTP 客户端调用 REST API：

```python
import httpx

MEM0_URL = "http://192.168.24.130:8888"
# 认证启用后取消下行注释
# HEADERS = {"X-API-Key": "m0sk_xxxxxxxx"}
HEADERS = {"Content-Type": "application/json"}

# 添加记忆
def add_memory(content: str, user_id: str):
    resp = httpx.post(f"{MEM0_URL}/memories", headers=HEADERS, json={
        "messages": [{"role": "user", "content": content}],
        "user_id": user_id,
    })
    return resp.json()

# 搜索记忆
def search_memory(query: str, user_id: str, top_k: int = 5):
    resp = httpx.post(f"{MEM0_URL}/search", headers=HEADERS, json={
        "query": query,
        "user_id": user_id,
        "top_k": top_k,
    })
    return resp.json()

# 使用示例
result = add_memory("我正在学习 Rust，喜欢用 Vim", "user-001")
print(result)

memories = search_memory("编程语言偏好", "user-001")
for m in memories["results"]:
    print(f"- {m['memory']} (score: {m.get('score', 'N/A')})")
```

### 12.4 方式三：TypeScript / Node.js 直接调用

```typescript
const MEM0_URL = "http://192.168.24.130:8888";
const HEADERS = { "Content-Type": "application/json" };
// 认证启用后: const HEADERS = { "Content-Type": "application/json", "X-API-Key": "m0sk_xxx" };

// 添加记忆
async function addMemory(content: string, userId: string) {
  const res = await fetch(`${MEM0_URL}/memories`, {
    method: "POST",
    headers: HEADERS,
    body: JSON.stringify({
      messages: [{ role: "user", content }],
      user_id: userId,
    }),
  });
  return res.json();
}

// 搜索记忆
async function searchMemory(query: string, userId: string) {
  const res = await fetch(`${MEM0_URL}/search`, {
    method: "POST",
    headers: HEADERS,
    body: JSON.stringify({ query, user_id: userId }),
  });
  return res.json();
}
```

### 12.5 方式四：OpenAI Function Calling 集成

将 mem0 挂载为 LLM Agent 的工具函数，让 Agent 自动决定何时存取记忆：

```python
import httpx
import json
from openai import OpenAI

MEM0_URL = "http://192.168.24.130:8888"

tools = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "保存用户信息、偏好、重要事实到长期记忆中",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "要保存的内容"},
                    "user_id": {"type": "string", "description": "用户 ID"},
                },
                "required": ["content", "user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "搜索用户的长期记忆，查找相关信息、偏好或历史",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索查询"},
                    "user_id": {"type": "string", "description": "用户 ID"},
                },
                "required": ["query", "user_id"],
            },
        },
    },
]


def call_mem0_tool(function_name: str, arguments: dict):
    args = json.loads(arguments) if isinstance(arguments, str) else arguments
    if function_name == "save_memory":
        resp = httpx.post(f"{MEM0_URL}/memories", json={
            "messages": [{"role": "user", "content": args["content"]}],
            "user_id": args["user_id"],
        })
        return json.dumps(resp.json())
    elif function_name == "search_memory":
        resp = httpx.post(f"{MEM0_URL}/search", json={
            "query": args["query"],
            "user_id": args["user_id"],
        })
        return json.dumps(resp.json())


# Agent 对话循环示例
client = OpenAI()
messages = [
    {"role": "system", "content": "你是一个有记忆能力的 AI 助手。在对话中主动使用工具保存和回忆用户信息。"},
]

def chat(user_input: str, user_id: str = "user-001"):
    messages.append({"role": "user", "content": user_input})

    # 第一步：让 Agent 搜索相关记忆
    memories_resp = httpx.post(f"{MEM0_URL}/search", json={
        "query": user_input, "user_id": user_id
    })
    memory_context = "\n".join(
        f"- {m['memory']}" for m in memories_resp.json().get("results", [])
    )

    system_msg = f"用户的历史记忆:\n{memory_context}\n\n请根据记忆和当前对话回复用户，并保存新的重要信息。"
    full_messages = [{"role": "system", "content": system_msg}] + messages

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=full_messages,
        tools=tools,
    )

    msg = response.choices[0].message
    if msg.tool_calls:
        for tc in msg.tool_calls:
            result = call_mem0_tool(tc.function.name, tc.function.arguments)
            messages.append(msg)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        # 再次调用获取最终回复
        response = client.chat.completions.create(model="gpt-4o-mini", messages=full_messages + messages[-len(msg.tool_calls)*2:])
        return response.choices[0].message.content

    return msg.content
```

### 12.6 方式五：LangChain / CrewAI / LangGraph 等框架

通过 REST API 封装为工具类，适配各种 Agent 框架：

```python
# LangChain Tool 示例
from langchain_core.tools import tool
import httpx

MEM0_URL = "http://192.168.24.130:8888"

@tool
def mem0_save(content: str, user_id: str) -> str:
    """保存信息到用户长期记忆。content 为要保存的内容，user_id 为用户标识。"""
    resp = httpx.post(f"{MEM0_URL}/memories", json={
        "messages": [{"role": "user", "content": content}],
        "user_id": user_id,
    })
    return resp.text

@tool
def mem0_recall(query: str, user_id: str) -> str:
    """从用户长期记忆中搜索相关信息。query 为搜索词，user_id 为用户标识。"""
    resp = httpx.post(f"{MEM0_URL}/search", json={
        "query": query, "user_id": user_id,
    })
    return resp.text

# 在 Agent 中使用
from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent

llm = ChatOpenAI(model="gpt-4o-mini")
tools = [mem0_save, mem0_recall]
# ... 构建 Agent
```

### 12.7 接入方式对比

| 方式 | 适用场景 | 复杂度 | 认证支持 |
|------|---------|:------:|---------|
| **REST API（curl）** | 测试 / 简单集成 | ⭐ | X-API-Key / Bearer JWT |
| **Python httpx** | Python Agent | ⭐⭐ | X-API-Key |
| **TypeScript fetch** | Node.js Agent | ⭐⭐ | X-API-Key |
| **OpenAI Function Calling** | ChatGPT 类 Agent | ⭐⭐⭐ | X-API-Key |
| **LangChain/CrewAI Tool** | Agent 框架集成 | ⭐⭐⭐ | X-API-Key |
| Python MemoryClient SDK | ❌ 不兼容自托管 | — | 使用 `Token` 格式，服务器不接受 |
| TypeScript MemoryClient SDK | ❌ 不兼容自托管 | — | 同上 |

> **为什么不兼容 MemoryClient SDK：** SDK 发送 `Authorization: Token xxx`，而自托管服务器校验 `Authorization: Bearer xxx` 或 `X-API-Key: xxx`。如需 SDK 接入，需用上方 httpx/fetch 方式自行封装。

---

## 13. 自托管 vs Cloud Platform 功能对比

| 功能 | 自托管 | Cloud Platform |
|------|:------:|:--------------:|
| 记忆 CRUD | ✅ | ✅ |
| 语义 + 关键词搜索 | ✅ | ✅ |
| Dashboard UI | ✅ | ✅ |
| API Key 管理 | ✅ | ✅ |
| 用户认证 | ✅ | ✅ |
| 自定义 LLM / Embedding | ✅ | ✅ |
| Webhooks | ❌ | ✅ |
| 记忆导出 | ❌ | ✅ |
| 高级分析 / 审计日志 | ❌ | ✅ |
| SSO / SAML | ❌ | ✅（Enterprise） |
| 多租户 / 项目隔离 | ❌ | ✅ |
| 自动扩缩容 / 高可用 | ❌ | ✅ |
| 记忆衰减（Memory Decay） | ❌ | ✅ |
