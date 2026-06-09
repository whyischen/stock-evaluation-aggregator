# Docker 化与工具接入状态

日期：2026-06-10

## 当前结论

SEA 需要编写并维护 `docker-compose.yml`。

原因：

- SEA Core 自身需要以 Web 服务方式部署。
- TradingAgents-CN、TradingAgents 等第三方工具应作为独立插件服务启动。
- 插件需要独立管理 API Key、模型 URL、超时时间和依赖环境。
- Docker Compose 可以把 SEA Core、插件服务、环境变量和内部网络一次性编排起来。

## 当前已完成

### SEA Core Docker 化

已新增：

- `Dockerfile`
- `docker-compose.yml`
- `.env.example`

`sea-core` 容器会启动：

```bash
uvicorn sea_api.main:app --host 0.0.0.0 --port 8000
```

Web 页面和 REST API 会通过同一个容器提供。

### 插件服务 Docker 编排

当前 Compose 中包含：

- `tradingagents-cn-svc`
- `tradingagents-svc`

两个插件服务都使用统一入口：

```bash
uvicorn plugins.service:app --host 0.0.0.0 --port 8080
```

通过环境变量区分插件：

```bash
SEA_PLUGIN_SERVICE_ID=tradingagents_cn
SEA_PLUGIN_SERVICE_ID=tradingagents
```

### SEA Core 到插件服务的连接

`sea-core` 通过环境变量读取插件 URL：

```bash
SEA_TRADINGAGENTS_CN_URL=http://tradingagents-cn-svc:8080
SEA_TRADINGAGENTS_URL=http://tradingagents-svc:8080
```

当 URL 存在时，SEA Core 会使用 HTTP transport 调用插件服务。

当 URL 不存在时，SEA Core 会回退到本地 adapter transport，方便本地开发。

## 第三方工具必填项如何填写

### 用户填写位置

用户应复制：

```bash
cp .env.example .env
```

然后在 `.env` 中填写第三方工具所需配置。

### LLM API Key

TradingAgents 系列通常需要至少一个 LLM Provider。

当前支持从环境变量读取：

```bash
OPENAI_API_KEY=
DEEPSEEK_API_KEY=
ANTHROPIC_API_KEY=
QWEN_API_KEY=
GOOGLE_API_KEY=
DASHSCOPE_API_KEY=
```

如果使用本地模型，可填写：

```bash
OLLAMA_BASE_URL=
```

### 是否允许真实调用

为了避免误触发 LLM 费用，真实 TradingAgents 调用默认关闭：

```bash
SEA_ENABLE_LIVE_TRADINGAGENTS=false
```

确认依赖和 API Key 都配置好后再改成：

```bash
SEA_ENABLE_LIVE_TRADINGAGENTS=true
```

### 插件 URL

Docker Compose 内部已经自动配置：

```bash
SEA_TRADINGAGENTS_CN_URL=http://tradingagents-cn-svc:8080
SEA_TRADINGAGENTS_URL=http://tradingagents-svc:8080
```

普通用户不需要手动填写。

如果不是用 Compose，而是接入远程插件服务，则需要手动设置这些 URL。

### 超时和权重

```bash
SEA_TRADINGAGENTS_CN_TIMEOUT_SECONDS=300
SEA_TRADINGAGENTS_TIMEOUT_SECONDS=300
SEA_TRADINGAGENTS_CN_WEIGHT=1.0
SEA_TRADINGAGENTS_WEIGHT=1.0
```

LLM 类插件通常耗时较长，默认超时为 300 秒。

## 当前未完成

### 上游依赖镜像尚未固化

当前 Dockerfile 安装的是 SEA 自身代码。

TradingAgents-CN 和 TradingAgents 的上游依赖尚未写入独立插件镜像，因此插件服务会正常启动，但在未安装上游包时 `/health` 会返回 `unavailable`。

后续需要为每个真实插件补专属镜像，例如：

- `docker/plugins/tradingagents-cn/Dockerfile`
- `docker/plugins/tradingagents/Dockerfile`

这些镜像应负责安装对应开源项目及其系统依赖。

### 插件配置还不是 UI 表单

当前必填项通过 `.env` 填写。

Web 页面暂时只展示插件状态，不负责录入 API Key。

这符合当前安全策略：API Key 不应在前端页面中明文输入和长期保存。

后续如需要 Web 配置，应做成后端加密存储或只引导用户编辑部署环境变量。

## 推荐使用流程

### 本地 Docker 启动

1. 复制环境文件：

```bash
cp .env.example .env
```

2. 填写 `.env`。

3. 启动：

```bash
docker compose up --build
```

4. 打开：

```text
http://127.0.0.1:8000/
```

5. 在系统状态中检查插件是否 ready。

### 真实插件接入前检查

插件 ready 需要同时满足：

- 插件服务容器可启动。
- 上游开源项目依赖已安装。
- LLM API Key 或本地模型 URL 已配置。
- `SEA_ENABLE_LIVE_TRADINGAGENTS=true`。
- 插件 `/health` 返回 ready。

## 技术指标完成度

| 指标 | 状态 |
| --- | --- |
| SEA Core Docker 部署 | 已完成基础版 |
| Web 页面随 SEA Core 部署 | 已完成 |
| 插件服务独立容器 | 已完成骨架 |
| SEA Core 通过 HTTP 调用插件服务 | 已完成 |
| `.env` 管理 API Key / URL / 超时 | 已完成基础版 |
| TradingAgents-CN 专属依赖镜像 | 未完成 |
| TradingAgents 专属依赖镜像 | 未完成 |
| Web 页面配置 API Key | 暂不建议做 |
| Qlib / RD-Agent Docker 服务 | 未开始 |

## 下一步

1. 为 TradingAgents-CN 编写专属 Dockerfile。
2. 为 TradingAgents 编写专属 Dockerfile。
3. 在插件容器中安装对应开源项目并验证真实 `/health`。
4. 使用 `.env` 配置真实 LLM Key 后验证 `/evaluate`。
5. 再进入 Qlib / RD-Agent 的 Docker 化设计。
