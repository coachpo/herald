# Herald

[English](README.md) | 简体中文

Herald 是面向单用户的通知收件箱与持久化转发服务。一个进程提供仪表盘和 HTTP API，使用 SQLite 保存消息，并向 Bark、ntfy、MQTT 或 Gotify 投递。

外部接入统一使用 HTTP JSON `POST /api/ingest`，MQTT 用于向外投递。此版本移除了 PostgreSQL 服务、多用户账户、规则与模板、Edge 中继及其旧 API；仪表盘发送复用同一个持久化接收操作。

只有消息及所选目标的投递任务全部提交后，接入请求才会成功返回。失败任务自动重试，仪表盘展示各目标状态，并允许人工重试最终失败的任务。投递保证为**至少一次**：供应商收到消息后进程崩溃，恢复时可能重复投递。

## 启动

需要 Python 3.13+、uv、Node.js 24 和 Corepack。从仓库根目录运行：

```bash
./start.sh
```

脚本安装锁定依赖、构建仪表盘，然后一起启动 API 与投递循环。仪表盘使用 8000 端口。需要独立 Vite 热更新时运行 `./start.sh dev`，Vite 在 35173 端口代理到 8000 端口的 API。两种模式都不会终止其他已有监听进程。

首次启动创建 `data/herald.sqlite3` 及私有文件 `data/credentials.env`。可用 `HERALD_DATA_DIR` 指定其他持久目录。请私下从该文件取得 `HERALD_ADMIN_TOKEN` 登录仪表盘；发送方使用独立的 `HERALD_INGEST_TOKEN`。不要分享加密密钥。不需要注册、邮箱、外部数据库或独立 worker。

也可运行使用持久数据卷的单容器：

```bash
docker compose up -d --build
```

配置、凭据访问、备份恢复及升级方法见[运维文档](docs/07_operations.md)。此版本创建新的 SQLite 存储，不导入旧数据库。

## 发送

先在仪表盘创建至少一个启用的默认目标，再使用已安全配置到当前 shell 的接入令牌发送 JSON：

```bash
curl --fail-with-body -X POST http://127.0.0.1:8000/api/ingest \
  -H "Authorization: Bearer $HERALD_INGEST_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"备份","body":"备份已完成","priority":3,"idempotency_key":"backup-2026-11-09"}'
```

使用 `target_ids` 可明确指定目标；省略时选择所有已启用的默认目标，空目标集合会被拒绝。相同幂等键和相同内容返回原结果，同键不同内容返回 `409`。省略幂等键则每次创建新消息。`201` 表示已存储等待投递，不表示已送达。

## 验证

```bash
uv sync --project backend --locked
uv run --project backend --locked pytest backend/tests -q
corepack pnpm@10.30.1 --dir frontend install --frozen-lockfile
corepack pnpm@10.30.1 --dir frontend lint
corepack pnpm@10.30.1 --dir frontend build
python3 scripts/sync_version.py --check
```

测试使用临时 SQLite 文件，供应商网络请求使用模拟传输。

## 文档

- [架构](docs/02_architecture.md)：进程职责和投递流程
- [数据模型](docs/03_data_model.md)：持久记录和清理边界
- [API](docs/04_api_spec.md)：请求、认证和投递状态
- [安全](docs/06_security_privacy.md)：凭据、出站保护和隐私
- [运维](docs/07_operations.md)：启动、配置、备份和恢复
- [仓库指南](docs/09_repo_structure.md)：源码职责和开发原则
