# SEA Web First 执行计划

## 1. 目标定位

SEA 的核心目标不是自己完成股票评估，而是提供一个轻量化的开源项目接入、编排和结果展示平台。

项目应围绕三件事展开：

1. 接入外部开源项目：TradingAgents、TradingAgents-CN、Qlib、RD-Agent 等。
2. 编排外部能力：根据标的、市场、插件状态并发调用插件，并处理超时和失败。
3. 展示评估结果：用 Web 页面清楚呈现不同插件的观点、置信度、理由、分歧和原始输出。

MVP 阶段不做 CLI，不做复杂 SDK，不做 SEA 自有评估逻辑。

## 2. 产品范围

### 2.1 MVP 必做

- Web 评估页面
- SEA Core REST API
- 插件统一协议
- 插件编排器
- Mock 插件服务
- TradingAgents-CN 插件接入
- TradingAgents 插件接入
- 标准化结果展示
- 插件健康状态展示
- 评估历史的最小持久化

### 2.2 MVP 暂缓

- CLI 工具
- Python SDK
- 第三方插件脚手架
- Markdown / PDF 报告导出
- 完整 Docker 化生产部署
- Qlib 数据初始化、训练和批量预测
- RD-Agent 自动研究任务
- 用户系统、权限系统、多人协作

### 2.3 明确不做

- SEA 自研股票评估算法
- SEA 自研交易信号模型
- 交易执行、下单、资金管理
- 将聚合分数包装成投资建议

## 3. 架构原则

### 3.1 SEA Core 保持轻量

SEA Core 只负责：

- 接收 Web 请求
- 读取插件配置
- 选择插件
- 并发调用插件
- 标准化收集结果
- 生成展示用报告结构
- 保存必要历史记录

SEA Core 不负责：

- 分析财报
- 计算技术指标
- 训练模型
- 编写因子
- 判断股票是否值得买入

### 3.2 插件承担评估能力

每个外部开源项目通过插件服务接入 SEA。

插件服务负责：

- 调用对应开源项目
- 解析原始输出
- 转换为 SEA 标准结果
- 暴露健康检查
- 保留插件原始 detail

### 3.3 Web 是主入口

普通用户只通过 Web 页面使用 SEA。

Web 页面负责：

- 搜索或选择标的
- 发起评估
- 展示插件状态
- 展示多插件横向对比
- 展示共识、分歧和失败原因
- 展示插件原始解释内容

## 4. 推荐系统形态

```text
Browser Web UI
      |
      v
SEA Core REST API
      |
      v
Orchestrator
      |
      +--> TradingAgents-CN Plugin Service
      +--> TradingAgents Plugin Service
      +--> Mock Plugin Service
      +--> Qlib Plugin Service       future
      +--> RD-Agent Research Service future
```

## 5. 核心数据契约

### 5.1 EvaluationTask

表示一次评估请求。

字段建议：

- `ticker`
- `eval_date`
- `market`
- `plugin_ids`
- `config_overrides`

### 5.2 PluginResult

表示单个插件返回的结果。

字段建议：

- `plugin_id`
- `plugin_name`
- `ticker`
- `eval_date`
- `direction`: `BUY` / `HOLD` / `SELL` / `UNKNOWN`
- `confidence`: `0.0 - 1.0`
- `summary`
- `detail`
- `raw_output_ref`
- `latency_ms`
- `status`: `success` / `failed` / `timeout` / `unavailable`
- `error`
- `signal_age_days`

### 5.3 EvalReport

表示前端展示用的统一报告。

字段建议：

- `ticker`
- `eval_date`
- `results`
- `success_count`
- `failed_count`
- `direction_counts`
- `consensus_level`
- `weighted_score`
- `divergence_notes`
- `created_at`

## 6. 插件 HTTP 协议

### 6.1 健康检查

```http
GET /health
```

返回：

```json
{
  "plugin_id": "tradingagents_cn",
  "status": "ready",
  "message": "ready",
  "latency_ms": 12,
  "capabilities": {
    "markets": ["A_SHARE"],
    "plugin_type": "realtime"
  }
}
```

### 6.2 执行评估

```http
POST /evaluate
```

请求：

```json
{
  "ticker": "600519.SS",
  "eval_date": "2026-06-09",
  "config": {}
}
```

返回：

```json
{
  "plugin_id": "tradingagents_cn",
  "ticker": "600519.SS",
  "eval_date": "2026-06-09",
  "direction": "BUY",
  "confidence": 0.71,
  "summary": "白酒板块回暖，公司基本面稳定，中线偏乐观。",
  "detail": {},
  "latency_ms": 42000,
  "status": "success",
  "error": null
}
```

## 7. 阶段计划

## Phase 0：项目工程骨架

目标：建立 Web First 项目的基础结构。

任务：

- 初始化 Python 项目结构。
- 建立 `sea_core` 包。
- 建立 `sea_api` REST API。
- 建立 `web` 前端目录。
- 建立测试目录。
- 引入基础依赖：FastAPI、Pydantic v2、httpx、pytest、SQLite 相关库。
- 暂不引入 Typer / Rich。

建议目录：

```text
sea_core/
  models/
  config/
  registry/
  orchestrator/
  report/
  storage/

sea_api/
  main.py
  routes/

plugins/
  mock/
  tradingagents_cn/
  tradingagents/

web/
  src/
```

验收标准：

- 后端服务可以启动。
- `GET /health` 返回正常。
- 测试框架可以运行。

## Phase 1：插件协议与 Mock 编排闭环

目标：在不接真实开源项目的情况下，先跑通完整链路。

任务：

- 定义 `EvaluationTask`。
- 定义 `PluginResult`。
- 定义 `EvalReport`。
- 定义插件 manifest 配置格式。
- 实现插件注册表。
- 实现 HTTP 插件客户端。
- 实现 Orchestrator。
- 实现 2 到 3 个 Mock 插件服务。
- 实现 `POST /evaluate`。
- 实现 `GET /plugins`。

验收标准：

- Web 或 API 可以发起一次评估。
- SEA Core 能并发调用多个 Mock 插件。
- 某个 Mock 插件失败时，整体评估仍然成功返回。
- 返回结果包含成功插件、失败插件、耗时和错误原因。

## Phase 2：Web 评估页接入真实 API

目标：将原型中的评估页从静态 mock 数据改为调用 SEA Core API。

任务：

- 保留原型图 v4 的主要信息架构。
- 实现搜索标的输入。
- 实现自选标的列表的前端状态。
- 调用 `POST /evaluate`。
- 展示插件结果矩阵。
- 展示共识、方向统计和加权分数。
- 支持展开单个插件详情。
- 支持失败插件状态展示。

验收标准：

- 用户可以在 Web 页面输入 ticker 并发起评估。
- 页面展示多个插件结果。
- 页面可以展示插件失败、超时和不可用。
- 页面不依赖写死的 mock result。

## Phase 3：接入 TradingAgents-CN

目标：接入第一个真实开源评估源，优先服务 A 股场景。

任务：

- 调研 TradingAgents-CN 当前调用方式。
- 编写插件服务包装。
- 实现 `/health`。
- 实现 `/evaluate`。
- 将 TradingAgents-CN 原始输出转换为 `PluginResult`。
- 保留原始报告内容到 `detail` 或 `raw_output_ref`。
- 处理 API Key 缺失、依赖缺失、调用超时。
- 在 SEA Core 中配置 A 股默认路由。

验收标准：

- `600519.SS` 可以通过 TradingAgents-CN 插件完成评估。
- Web 页面可以展示 TradingAgents-CN 的方向、置信度、摘要和详情。
- 插件不可用时，Web 页面展示明确原因。

## Phase 4：接入 TradingAgents

目标：接入美股实时评估能力。

任务：

- 编写 TradingAgents 插件服务包装。
- 实现 `/health`。
- 实现 `/evaluate`。
- 将原始输出转换为 `PluginResult`。
- 在 SEA Core 中配置美股默认路由。
- 支持用户在 Web 页面启用或禁用插件参与本次评估。

验收标准：

- `AAPL` 可以通过 TradingAgents 插件完成评估。
- A 股和美股走不同默认插件策略。
- 用户可以看到每个插件是否参与了本次评估。

## Phase 5：评估历史与关注列表

目标：形成基础产品闭环。

任务：

- 设计 SQLite schema。
- 保存每次评估请求。
- 保存每个插件返回结果。
- 保存关注标的。
- 实现 `GET /history`。
- 实现 `GET /watchlist`。
- 实现 `POST /watchlist`。
- 实现 `DELETE /watchlist/{ticker}`。
- Web 页面接入关注列表和最近评估。

验收标准：

- 刷新页面后关注列表仍然存在。
- 用户可以查看最近评估。
- 每次评估结果可以追溯到具体插件输出。

## Phase 6：系统监控页面

目标：把插件接入状态变成用户可理解的信息。

任务：

- 实现插件健康检查聚合。
- 实现 `GET /system/status`。
- Web 系统监控页展示插件状态。
- 展示插件服务延迟。
- 展示插件不可用原因。
- 展示插件支持市场。

验收标准：

- 用户可以从 Web 页面判断当前哪些插件可用。
- API Key 缺失、服务未启动、超时等状态有明确展示。

## Phase 7：Qlib Cached Plugin

目标：将 Qlib 作为基于预计算信号的查询插件接入，而不是一开始承担训练系统。

任务：

- 定义 Qlib 信号文件格式。
- 实现 Qlib 插件状态机。
- 实现已有信号查询。
- 实现 Alpha 到 Direction 的插件内部映射。
- 返回 `signal_age_days`。
- 展示信号新鲜度和覆盖率。

验收标准：

- Qlib 插件可以对已覆盖标的返回量化信号。
- 信号过期时，SEA 可以展示 stale 状态。
- SEA Core 不包含 Qlib 评估逻辑。

## Phase 8：RD-Agent 研究管理

目标：将 RD-Agent 定位为离线研究任务，不进入实时评估链路。

任务：

- 实现研究任务触发 API。
- 实现研究任务状态查询 API。
- 保存研究任务历史。
- Web 研究管理页展示任务状态。
- 研究完成后刷新 Qlib 信号状态。

验收标准：

- RD-Agent 运行中不阻塞实时评估。
- 研究任务状态可以在 Web 页面查看。
- RD-Agent 的产出通过 Qlib 信号进入评估展示。

## 8. MVP 推荐任务清单

第一批任务建议只覆盖 Phase 0 到 Phase 2。

### EPIC-A：工程骨架

- `A-001` 初始化 Python / FastAPI 项目。
- `A-002` 建立核心包结构。
- `A-003` 配置项目依赖和测试框架。
- `A-004` 实现后端健康检查接口。

### EPIC-B：核心数据契约

- `B-001` 定义 `Direction`。
- `B-002` 定义 `EvaluationTask`。
- `B-003` 定义 `PluginResult`。
- `B-004` 定义 `EvalReport`。
- `B-005` 编写模型序列化测试。

### EPIC-C：插件编排

- `C-001` 定义插件 manifest 格式。
- `C-002` 实现插件注册表。
- `C-003` 实现 HTTP 插件客户端。
- `C-004` 实现 Orchestrator 并发调用。
- `C-005` 实现超时和失败隔离。

### EPIC-D：Mock 插件

- `D-001` 实现 Mock Bullish 插件。
- `D-002` 实现 Mock Bearish 插件。
- `D-003` 实现 Mock Failure 插件。
- `D-004` 编写 Mock 插件服务测试。

### EPIC-E：评估 API

- `E-001` 实现 `POST /evaluate`。
- `E-002` 实现 `GET /plugins`。
- `E-003` 实现 `GET /system/status` 的最小版本。
- `E-004` 编写 API 集成测试。

### EPIC-F：Web 评估页

- `F-001` 建立前端工程。
- `F-002` 迁移原型图 v4 的评估页布局。
- `F-003` 接入 `POST /evaluate`。
- `F-004` 展示插件结果矩阵。
- `F-005` 展示共识和分歧。
- `F-006` 展示插件详情展开。
- `F-007` 展示插件失败状态。

## 9. 开发优先级

优先级从高到低：

1. 插件协议
2. 编排器
3. 标准结果模型
4. Web 评估页
5. TradingAgents-CN 接入
6. TradingAgents 接入
7. 评估历史
8. 系统监控
9. Qlib cached plugin
10. RD-Agent 研究管理

## 10. 判断标准

每个阶段都用同一个问题验收：

> 这个阶段是否让 SEA 更好地接入外部开源项目，并更清楚地展示外部项目的结果？

如果答案是否定的，该任务应推迟或删除。

## 11. 近期建议

下一步直接开始 Phase 0 和 Phase 1。

不要先做：

- CLI
- 完整 Docker Compose
- Qlib 训练流程
- RD-Agent 自动研究
- 插件脚手架

先完成：

- Web First 后端骨架
- 插件协议
- Mock 插件
- 编排闭环
- Web 评估页接入 API

这样可以尽快验证 SEA 的核心价值：轻量接入多个开源项目，并把它们的结果清楚地展示给用户。
