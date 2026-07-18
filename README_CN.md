# Herald

[English](README.md) | 简体中文

Herald 是一个自托管的通知中枢:把所有机器、脚本和服务的通知汇入一个收件箱,再分发到你常用的通知应用。它通过 HTTP 接收结构化 JSON,把消息存入 PostgreSQL,并将命中规则的消息转发到 Bark、ntfy、MQTT 或 Gotify。

## 包结构

- `backend/`:FastAPI API、数据库迁移、PostgreSQL 访问、认证、接入与投递 worker
- `frontend/`:React 19 + Vite 仪表盘
- `edge/`:Cloudflare 与 EdgeOne 存储转发中继

## 功能

- 邮箱/密码认证,支持 refresh token 轮换、账户管理与 CLI 重置密码
- 多个接入端点,使用一次性明文密钥
- 可浏览的消息历史,支持过滤、详情查看、软删除与批量删除
- Bark、ntfy、MQTT、Gotify 四种通知通道
- 投递规则按消息 body、priority、group 匹配,支持每条规则的 payload 模板
- endpoint 和 tag 过滤器可在 UI 与预览 API 中保存和测试
- 持久化的 Cloudflare 中继与 EdgeOne KV 中继,用于跨境接入

## 快速开始

```bash
./start.sh headless
./start.sh full
```

从仓库根目录手动启动后端:

```bash
uv sync --project backend --locked
uv run --project backend --locked python -m backend.migrate
uv run --project backend --locked herald-backend
uv run --project backend --locked python -m backend.worker
```

生产环境 compose:

```bash
cp .env.example .env
chmod 600 .env
# 修改 POSTGRES_PASSWORD、SECRET_KEY 和 CHANNEL_CONFIG_ENCRYPTION_KEY
docker compose up -d
```

## 文档

- `docs/01_prd.md`:产品范围
- `docs/02_architecture.md`:运行时架构
- `docs/03_data_model.md`:数据库表
- `docs/04_api_spec.md`:API 指南
- `docs/openapi.yaml`:生成的 OpenAPI schema
- `docs/06_security_privacy.md`:密钥、信任边界、SSRF
- `docs/07_operations.md`:部署与运维
- `docs/10_edge.md`:Cloudflare 与 EdgeOne 中继协议

## 验证

```bash
docker start herald-test-pg 2>/dev/null || docker run -d --name herald-test-pg -e POSTGRES_DB=herald -e POSTGRES_USER=herald -e POSTGRES_PASSWORD=herald -p 5432:5432 postgres:16-alpine
uv run --project backend --locked pytest backend/tests -v
npm --prefix edge test && npm --prefix edge run lint
corepack pnpm@10.30.1 --dir frontend lint
corepack pnpm@10.30.1 --dir frontend build
python3 scripts/sync_version.py --check
```

后端测试读取 `TEST_DATABASE_URL`,默认为 `postgresql://herald:herald@127.0.0.1:5432/herald`。
