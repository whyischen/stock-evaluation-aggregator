# Stock Evaluation Aggregator

SEA is a lightweight Web First orchestration layer for connecting open-source stock evaluation projects and presenting their results side by side.

SEA does not implement stock evaluation logic. It calls plugins, collects standardized results, and renders comparison reports.

## 必备资源：Docker

Docker 和 Docker Compose 是运行 SEA 的必要条件，不是可选项。

SEA 的标准运行方式是 Docker Compose 多容器部署。`docker-compose.yml` 是整个系统的核心配置文件，它定义了 SEA 的服务架构、镜像构建、服务发现、环境变量、端口暴露、数据卷和容器间依赖关系。日常部署、联调和排障都应以 `docker compose ...` 命令为入口。

必须确认本机已安装：

- Docker
- Docker Compose v2，即可使用 `docker compose ...` 命令

本地非 Docker 运行只适合开发核心 API 时临时调试，不能替代完整 SEA 运行环境，因为插件服务、服务发现和容器隔离都由 Docker Compose 提供。

## 5 分钟快速开始

### 1. 准备环境变量

```bash
cp .env.example .env
```

首次启动可以保持默认 mock 配置：

```bash
SEA_ENABLE_MOCK_PLUGINS=true
SEA_ENABLE_LIVE_TRADINGAGENTS=false
```

这会避免真实调用 LLM 和上游 TradingAgents 项目，适合快速验证系统是否跑通。

### 2. 构建并启动全部服务

```bash
docker compose up -d --build
```

该命令会根据 `docker-compose.yml` 构建并启动 3 个容器：

- `sea-core`
- `tradingagents-cn-svc`
- `tradingagents-svc`

### 3. 验证服务状态

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/system/status
```

核心服务健康检查预期返回：

```json
{"status":"ok","service":"sea-core"}
```

### 4. 发送一次评估请求

A 股示例：

```bash
curl -X POST http://localhost:8000/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "600519.SS",
    "eval_date": "2026-06-10",
    "market": "A_SHARE"
  }'
```

美股示例：

```bash
curl -X POST http://localhost:8000/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "eval_date": "2026-06-10",
    "market": "US"
  }'
```

接口同时支持 `/api/evaluate` 和 `/evaluate`。

## Docker Compose 是核心配置项

`docker-compose.yml` 是 SEA 的部署事实来源。它定义了：

| 配置范围 | 说明 |
| --- | --- |
| 服务架构 | 1 个核心服务 `sea-core` + 2 个插件服务 `tradingagents-cn-svc`、`tradingagents-svc` |
| 镜像构建 | 核心服务使用 `Dockerfile.core`，插件服务使用 `Dockerfile.plugin` |
| Python 版本 | 核心服务基于 Python 3.11，插件服务基于 Python 3.12 |
| 服务发现 | `sea-core` 通过 Compose 内部 DNS 访问插件服务名 |
| 网络边界 | 只有 `sea-core` 暴露宿主机端口 `8000`，插件服务只在 Compose 网络内部访问 |
| 数据持久化 | SQLite 数据库挂载到 Docker volume `sea_data` |
| 插件身份 | 两个插件容器通过 `SEA_PLUGIN_SERVICE_ID` 区分加载的 adapter |
| 运行配置 | `.env` 和 Compose `environment` 共同控制 mock、真实调用、超时、权重和 LLM Provider |

当前服务定义：

| 服务 | 镜像 | 端口 | 职责 | 技术栈 / 持久化 |
| --- | --- | --- | --- | --- |
| `sea-core` | `sea-core:local`，基于 `Dockerfile.core` 和 `python:3.11-slim` | `8000:8000`，对外暴露 | 接收评估请求，分发给插件服务，收集结果并聚合报告 | FastAPI + `asyncio` 并发调度；SQLite 持久化到 Docker volume `sea_data` |
| `tradingagents-cn-svc` | `sea-plugin-tradingagents-cn:local`，基于 `Dockerfile.plugin` 和 `python:3.12-slim` | `8080`，仅 Docker 内部网络 | 封装 TradingAgents-CN，提供 A 股评估能力 | 环境变量 `SEA_PLUGIN_SERVICE_ID=tradingagents_cn` |
| `tradingagents-svc` | `sea-plugin-tradingagents:local`，基于 `Dockerfile.plugin` 和 `python:3.12-slim` | `8080`，仅 Docker 内部网络 | 封装 TradingAgents，提供美股 / 港股评估能力 | 环境变量 `SEA_PLUGIN_SERVICE_ID=tradingagents` |

## 部署架构

```text
                         Host Machine
                              |
                              | http://localhost:8000
                              v
                  +---------------------------+
                  | Docker Compose Network    |
                  |                           |
                  |  +---------------------+  |
User / Web UI --->|  | sea-core            |  |
API Client        |  | Python 3.11         |  |
                  |  | FastAPI :8000       |  |
                  |  | SQLite -> sea_data  |  |
                  |  +----------+----------+  |
                  |             |             |
                  |             | HTTP        |
                  |             |             |
                  |    +--------+--------+    |
                  |    |                 |    |
                  |    v                 v    |
                  | +----------------+ +----------------+ |
                  | | tradingagents- | | tradingagents- | |
                  | | cn-svc         | | svc            | |
                  | | Python 3.12    | | Python 3.12    | |
                  | | :8080 internal | | :8080 internal | |
                  | | A-share        | | US / HK        | |
                  | +----------------+ +----------------+ |
                  |                           |
                  +---------------------------+
```

请求链路：

```text
用户 / Web UI / API Client
        |
        v
sea-core :8000
        |
        +--> http://tradingagents-cn-svc:8080
        |
        +--> http://tradingagents-svc:8080
```

`sea-core` 只负责编排、调度、聚合和展示，不内置股票评估判断。所有方向、置信度、摘要和明细都来自插件服务或本地 adapter。

## 为什么采用 3 个独立容器

SEA 当前采用 `sea-core + 2 个插件服务` 的多容器架构，这不是为了增加部署复杂度，而是为了让核心编排层和第三方评估能力保持清晰边界。

### 隔离性

插件服务独立运行。TradingAgents 或 TradingAgents-CN 的依赖冲突、运行异常、超时或 LLM 调用失败，不应拖垮 `sea-core`。核心服务会记录失败插件结果，并继续处理其他可用插件返回的结论。

### 可扩展性

插件服务是无状态 HTTP 服务，可以独立扩缩容。A 股请求量增加时，可以优先扩展 `tradingagents-cn-svc`；美股 / 港股请求量增加时，可以扩展 `tradingagents-svc`，不需要同时扩展核心服务。

### 技术栈分离

`sea-core` 使用 Python 3.11，保持核心 API、调度、聚合和持久化环境稳定。插件服务使用 Python 3.12，以满足 TradingAgents 相关上游项目的运行要求。不同 Python 版本和依赖集合被隔离在各自镜像内，避免在同一个解释器环境中互相污染。

### 资源管理

每个服务都可以独立限制 CPU、内存和重启策略。真实 TradingAgents 调用通常会消耗更多网络、LLM 和运行时资源，适合与核心服务分开管理。生产部署时可在 Compose 或编排平台中为插件服务单独配置资源限制。

## 服务间通信设计

- `sea-core` 通过 HTTP 调用插件服务的 `GET /health` 和 `POST /evaluate` 端点。
- 插件服务地址通过环境变量配置：
  - `SEA_TRADINGAGENTS_CN_URL=http://tradingagents-cn-svc:8080`
  - `SEA_TRADINGAGENTS_URL=http://tradingagents-svc:8080`
- Docker Compose 内部 DNS 会自动解析 `tradingagents-cn-svc` 和 `tradingagents-svc` 服务名。
- 当上述 URL 环境变量未设置时，`sea-core` 会回退到 in-process adapter 模式，直接在核心进程内调用本地适配器。
- 支持 Mock 模式：`SEA_ENABLE_MOCK_PLUGINS=true` 时会注册 mock 插件，便于本地开发、接口联调和无 LLM Key 的测试。

## 插件服务设计

两个插件服务使用相同的 `Dockerfile.plugin` 和同一套代码，通过 `SEA_PLUGIN_SERVICE_ID` 区分运行身份：

- `SEA_PLUGIN_SERVICE_ID=tradingagents_cn`：加载 TradingAgents-CN adapter，服务 A 股 ticker，例如 `600519.SS`。
- `SEA_PLUGIN_SERVICE_ID=tradingagents`：加载 TradingAgents adapter，服务美股 / 港股 ticker，例如 `AAPL`。

插件服务是无状态的，可独立扩缩容。每个插件服务暴露统一接口：

- `GET /health`：健康检查，返回服务可用性和插件身份。
- `POST /evaluate`：接收标准化评估任务，返回标准化插件结果。

## TradingAgents 插件说明

SEA 默认注册两个真实 adapter 插槽：

- `tradingagents_cn` for A-share tickers such as `600519.SS`
- `tradingagents` for US/HK tickers such as `AAPL`

Live calls are disabled by default to avoid accidental LLM cost. To enable them, install the corresponding upstream project in the runtime environment, configure an LLM provider, and set:

```bash
export SEA_ENABLE_LIVE_TRADINGAGENTS=true
export OPENAI_API_KEY=...
```

The adapters expect the upstream project to expose:

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

graph = TradingAgentsGraph(debug=False, config=DEFAULT_CONFIG)
state, decision = graph.propagate("AAPL", "2026-06-09")
```

在 Docker 部署中，`SEA_ENABLE_LIVE_TRADINGAGENTS=false` 是默认值，目的是避免误触发 LLM 调用成本。只有在插件镜像或运行环境中已经安装对应上游项目，并完成 LLM Provider 配置后，才建议开启真实调用。

## 配置说明

### 核心配置

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `SEA_ENABLE_MOCK_PLUGINS` | `true` | 是否启用 mock 插件。开发测试建议开启；生产或真实评估可关闭。 |
| `SEA_DB_PATH` | `/data/sea.sqlite3` | SQLite 数据库路径。Docker Compose 中挂载到 `sea_data` volume。 |
| `SEA_TRADINGAGENTS_CN_URL` | `http://tradingagents-cn-svc:8080` | A 股插件服务 HTTP 地址。未设置时回退到 in-process adapter。 |
| `SEA_TRADINGAGENTS_URL` | `http://tradingagents-svc:8080` | 美股 / 港股插件服务 HTTP 地址。未设置时回退到 in-process adapter。 |
| `SEA_ENABLE_LIVE_TRADINGAGENTS` | `false` | 是否允许真实调用 TradingAgents 上游库。默认关闭以避免 LLM 成本。 |

### LLM Provider 配置

`.env` 中只需要填写计划使用的 Provider：

| Provider | 关键配置 |
| --- | --- |
| OpenAI | `OPENAI_API_KEY`，可配合 `SEA_TRADINGAGENTS_CONFIG__LLM_PROVIDER=openai` |
| Anthropic | `ANTHROPIC_API_KEY` |
| DashScope / Qwen | `DASHSCOPE_API_KEY` 或 `QWEN_API_KEY` |
| Google | `GOOGLE_API_KEY` |
| DeepSeek | `DEEPSEEK_API_KEY` |
| Ollama | `OLLAMA_BASE_URL` |

TradingAgents 配置会透传给上游库，SEA 不解释具体 Provider 字段。可以使用 JSON：

```bash
SEA_TRADINGAGENTS_CONFIG_JSON={"llm_provider":"openai","backend_url":"https://api.openai.com/v1","deep_think_llm":"gpt-4.1","quick_think_llm":"gpt-4.1-mini"}
SEA_TRADINGAGENTS_CN_CONFIG_JSON={"quick_provider":"dashscope","deep_provider":"dashscope","quick_api_key":"...","deep_api_key":"..."}
```

也可以使用双下划线配置项，它们会映射为小写 config key：

```bash
SEA_TRADINGAGENTS_CONFIG__LLM_PROVIDER=openai
SEA_TRADINGAGENTS_CONFIG__BACKEND_URL=https://api.openai.com/v1
SEA_TRADINGAGENTS_CONFIG__DEEP_THINK_LLM=gpt-4.1
SEA_TRADINGAGENTS_CONFIG__QUICK_THINK_LLM=gpt-4.1-mini

SEA_TRADINGAGENTS_CN_CONFIG__QUICK_PROVIDER=dashscope
SEA_TRADINGAGENTS_CN_CONFIG__DEEP_PROVIDER=dashscope
SEA_TRADINGAGENTS_CN_CONFIG__QUICK_API_KEY=...
SEA_TRADINGAGENTS_CN_CONFIG__DEEP_API_KEY=...
SEA_TRADINGAGENTS_CN_CONFIG__QUICK_MODEL=...
SEA_TRADINGAGENTS_CN_CONFIG__DEEP_MODEL=...
```

### 插件超时和权重

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `SEA_TRADINGAGENTS_CN_TIMEOUT_SECONDS` | `300` | A 股插件调用超时时间。 |
| `SEA_TRADINGAGENTS_TIMEOUT_SECONDS` | `300` | 美股 / 港股插件调用超时时间。 |
| `SEA_TRADINGAGENTS_CN_WEIGHT` | `1.0` | A 股插件聚合权重。 |
| `SEA_TRADINGAGENTS_WEIGHT` | `1.0` | 美股 / 港股插件聚合权重。 |

聚合时，SEA 会按照 `direction * confidence * weight` 计算加权分数。失败或超时的插件结果不会参与成功结果聚合，但会记录在报告中。

### Mock 模式

Mock 模式用于开发测试：

```bash
SEA_ENABLE_MOCK_PLUGINS=true
```

开启后，核心服务会额外注册 mock 插件，用于验证评估流程、聚合逻辑、历史记录和前端展示。关闭方式：

```bash
SEA_ENABLE_MOCK_PLUGINS=false
```

## 常用运维命令

查看容器状态：

```bash
docker compose ps
```

查看全部日志：

```bash
docker compose logs -f
```

查看指定服务日志：

```bash
docker compose logs -f sea-core
docker compose logs -f tradingagents-cn-svc
docker compose logs -f tradingagents-svc
```

重启服务：

```bash
docker compose restart sea-core
docker compose restart tradingagents-cn-svc
docker compose restart tradingagents-svc
```

停止并移除容器网络：

```bash
docker compose down
```

如需同时删除 SQLite 数据 volume：

```bash
docker compose down -v
```

查看评估历史：

```bash
curl "http://localhost:8000/api/history?limit=20"
```

按 ticker 查看历史：

```bash
curl "http://localhost:8000/api/history?ticker=AAPL&limit=20"
```

查看单条历史详情：

```bash
curl http://localhost:8000/api/history/1
```

## 故障排查

### `docker compose` 命令不存在

说明 Docker Compose v2 未安装或 Docker CLI 不可用。先确认：

```bash
docker --version
docker compose version
```

如果只有旧版 `docker-compose` 命令，建议升级 Docker Desktop 或 Docker Engine 的 Compose v2 插件。

### `localhost:8000` 无法访问

先检查容器是否启动：

```bash
docker compose ps
docker compose logs -f sea-core
```

常见原因：

- `sea-core` 构建失败或启动失败。
- 宿主机端口 `8000` 已被占用。
- `.env` 中配置错误导致应用启动异常。

如果端口冲突，可在 `docker-compose.yml` 中调整 `sea-core` 的端口映射，例如 `"8001:8000"`，然后访问 `http://localhost:8001`。

### 插件显示不可用

检查插件容器日志：

```bash
docker compose logs -f tradingagents-cn-svc
docker compose logs -f tradingagents-svc
```

再从核心服务查看系统状态：

```bash
curl http://localhost:8000/api/system/status
curl http://localhost:8000/api/plugins
```

常见原因：

- 插件容器未启动。
- `SEA_PLUGIN_SERVICE_ID` 配置错误。
- `sea-core` 中的插件 URL 未指向 Compose 服务名。
- 开启了 `SEA_ENABLE_LIVE_TRADINGAGENTS=true`，但插件镜像内未安装对应上游项目或缺少 LLM Provider 配置。

### 评估请求返回 mock 结果

确认 `.env`：

```bash
SEA_ENABLE_MOCK_PLUGINS=true
SEA_ENABLE_LIVE_TRADINGAGENTS=false
```

这是快速启动的默认行为。需要真实调用 TradingAgents / TradingAgents-CN 时，必须安装对应上游项目、配置 LLM Provider，并设置：

```bash
SEA_ENABLE_LIVE_TRADINGAGENTS=true
SEA_ENABLE_MOCK_PLUGINS=false
```

修改 `.env` 后重启服务：

```bash
docker compose up -d --build
```

### 真实 TradingAgents 调用失败

检查以下项目：

- 插件镜像或运行环境中是否安装了对应上游 TradingAgents / TradingAgents-CN 项目。
- `.env` 中是否填写了正确的 `OPENAI_API_KEY`、`DASHSCOPE_API_KEY`、`QWEN_API_KEY` 或其他 Provider Key。
- Provider 配置是否通过 `SEA_TRADINGAGENTS_CONFIG_JSON`、`SEA_TRADINGAGENTS_CN_CONFIG_JSON` 或双下划线配置传入。
- 插件超时时间是否足够，例如 `SEA_TRADINGAGENTS_TIMEOUT_SECONDS=300`。

### SQLite 数据丢失或需要清空

默认 SQLite 数据存放在 Docker volume `sea_data`。普通停止不会删除数据：

```bash
docker compose down
```

如果执行下面命令，会删除 volume 和历史数据：

```bash
docker compose down -v
```

### 修改 `.env` 后没有生效

Compose 环境变量在容器启动时注入。修改 `.env` 后需要重建或重启容器：

```bash
docker compose up -d --build
```

如只调整运行时环境变量且镜像无需重建，也可以：

```bash
docker compose up -d --force-recreate
```

## 本地非 Docker 运行

仅用于开发核心 API 的临时调试。完整运行 SEA 请使用 Docker Compose。

```bash
uvicorn sea_api.main:app --reload
```

然后打开 `http://127.0.0.1:8000`。
