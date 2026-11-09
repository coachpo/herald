# Herald

[English](README.md) | 简体中文

Herald 是一个自托管的通知中枢:把所有机器、脚本和服务的通知汇入一个收件箱,再分发到你常用的通知应用。它通过 HTTP 接收结构化 JSON,把消息存入 PostgreSQL,并将命中规则的消息转发到 Bark、ntfy、MQTT 或 Gotify。

## 包结构

- [`backend/`](backend/README.md):FastAPI API、数据库迁移、PostgreSQL 访问、认证、接入与投递 worker
- [`frontend/`](frontend/README.md):React 19 + Vite 仪表盘
- [`edge/`](edge/README.md):Cloudflare 与 EdgeOne 存储转发中继

## 功能

- 邮箱/密码认证,支持 refresh token 轮换、账户管理与 CLI 重置密码
- 多个接入端点,密钥可重复使用,但仅在创建时显示明文
- 可浏览的消息历史,支持过滤、详情查看、软删除与批量删除
- Bark、ntfy、MQTT、Gotify 四种通知通道
- 投递规则按消息 body、priority、group 匹配,支持每条规则的 payload 模板
- endpoint 和 tag 过滤器可保存和预览,但目前会导致实时规则不匹配；参见[规则限制](docs/04_api_spec.md#rules)
- 持久化的 Cloudflare 中继与 EdgeOne KV 中继,用于不可靠的网络路径

## 快速开始

从仓库根目录选择一种本地辅助启动模式。需要 Docker Compose、Python 3.13+、uv、`lsof` 和 `pgrep`；full 模式还要求 `PATH` 中有 Node 24 和 pnpm 10.30.1。

```bash
./start.sh headless  # PostgreSQL + API
# 或
./start.sh full      # PostgreSQL + API + 仪表盘
```

脚本默认停止 `35432`、`38000`、`35173` 端口已有的容器和监听进程,headless 模式也会清理前端端口。它**不启动投递 worker**。使用默认数据库端口时,请另开终端运行:

```bash
DATABASE_URL=postgresql://herald:herald@127.0.0.1:35432/herald_dev \
  uv run --project backend --locked python -m backend.worker
```

如果覆盖了 `DB_PORT`,相应修改 URL。端口和其他启动方式见[本地开发](docs/07_operations.md#local-development),手动启动见[后端快速开始](backend/README.md#quick-start)。生产环境请按[Production Compose](docs/07_operations.md#production-compose)配置,再单独部署前端和所需中继；根 Compose 文件只运行后端服务。

## 文档

以下文档分别维护详细约定；各包 README 作为定向入口,`AGENTS.md` 只提供代理操作指引,不重复项目手册。

| 权威内容 | 文档 |
| --- | --- |
| 产品意图、已实现范围、非目标 | [产品范围](docs/01_prd.md) |
| 当前组件与数据流、控制流 | [架构](docs/02_architecture.md) |
| 持久化 schema | [数据模型](docs/03_data_model.md) |
| HTTP 行为、通道配置、已知 API 限制 | [API 指南](docs/04_api_spec.md) |
| 浏览器路由与用户流程 | [UI 规范](docs/05_ui_spec.md) |
| 密钥、信任边界、安全与隐私约束 | [安全与隐私](docs/06_security_privacy.md) |
| 开发配置、验证命令、部署、备份与恢复 | [运维](docs/07_operations.md) |
| Bark payload 细节 | [Bark v2](docs/08_bark_v2.md) |
| 包边界与共享开发原则 | [仓库结构](docs/09_repo_structure.md) |
| 中继协议、平台配置与边缘运维流程 | [Edge 手册](docs/10_edge.md) |
| 生成的 schema 快照,不覆盖完整的手动 ingest 约定 | [OpenAPI](docs/openapi.yaml) |

仓库文档描述实现及预期流程,不能据此确定实际部署、用户数量、服务承诺或适用的数据保留义务。

## 验证

各包检查见[运维文档](docs/07_operations.md#local-development),与 [CI](.github/workflows/ci.yml)对应。后端测试会自动迁移并清空业务表：`TEST_DATABASE_URL` 只能指向专用可丢弃 PostgreSQL 测试库,不要使用需要保留数据的数据库。前端检查为 lint 与生产构建,edge 检查为测试与语法 lint；版本一致性检查为在仓库根目录运行 `python3 scripts/sync_version.py --check`。
