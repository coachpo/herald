# Herald 生产化升级 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Herald 升级为可部署上线、真实可用、健壮的跨境通知网关:后端修复致命缺陷并清除过度设计;新增 Cloudflare(DO 持久缓冲)与 EdgeOne(KV 存储转发)双边缘中继。

**Architecture:** 见 `docs/12_production_upgrade_design.md`(下称"设计文档",**执行前必须通读**)。核心:边缘只做存储转发中继,后端是唯一投递引擎;消息 id 在首个边缘铸造,后端 `ON CONFLICT DO NOTHING` 幂等;全链路用原始 ingest key 认证(边缘用新增的 `key_sha256` 离线验证)。

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy async + asyncpg / PostgreSQL 16;Cloudflare Workers + Durable Objects(SQLite)+ KV;EdgeOne Pages Edge Functions + KV;React 19 + Vite;`node --test`(边缘,零运行时依赖);pytest + pytest-asyncio。

## Global Constraints

- **零兼容**:所有者明确不保留数据、API、Django 遗留兼容。允许改表名、删表、删端点、重建数据库。禁止写任何兼容垫片/双读双写/迁移期开关。
- **不过度设计**:无单实现接口、无一消费者的层、无"以后可能用"的配置。新增抽象必须有 ≥2 个真实调用方。
- **依赖冻结**:后端不新增任何 Python 依赖(现有:asyncpg/cryptography/fastapi/httpx/paho-mqtt/PyJWT/sentry-sdk/sqlalchemy/structlog/uvicorn)。边缘保持零运行时依赖(devDep 仅 wrangler)。脚本只用 stdlib。
- **中间件约束**:后端所有中间件必须是纯 ASGI(禁 `BaseHTTPMiddleware`,asyncpg 连接与任务绑定,原因保留在 `backend/middleware.py` docstring)。Starlette 自带 `CORSMiddleware` 是纯 ASGI,允许。
- **命名**:环境变量 `SECRET_KEY`(不再是 `DJANGO_SECRET_KEY`);表名无前缀(`users`、`messages`…);中继头 `X-Herald-Message-Id` / `X-Herald-Received-At` / `X-Herald-Relay-Via`;边缘管理凭据 `RELAY_ADMIN_TOKEN`;同步凭据 `EDGE_SYNC_TOKEN`。
- **提交**:每个 Task 结束提交一次,Conventional Commits,message 用英文。
- 测试命令统一:后端 `uv run --project backend --locked pytest backend/tests -v`(需本地 Postgres,见 Task 0);边缘 `npm --prefix edge test`;前端 `pnpm --dir frontend lint && pnpm --dir frontend build`。

---

## 交接上下文(执行者从零起步所需)

**仓库现状关键事实**(2026-07-08,commit `6659ee7`):

- 后端无 ORM 模型:`backend/database.py` 运行时**反射** Django 风格表名(`accounts_user`、`beacon_message` 等,见 `database.py:91-101`);唯一 DDL 是 `backend/bootstrap_dev_db.py`(本计划将删除它)。
- `backend/config.py` 是 dataclass + `lru_cache(1)` 的 `get_settings()`(改 env 后必须 `get_settings.cache_clear()`);`.env` 从 `backend/.env` 读取。
- Worker 投递状态机词汇:`queued → sending → sent | failed | retry`;认领 SQL 在 `worker.py:34-77`(`FOR UPDATE SKIP LOCKED`,先置 `sending` 再处理)。
- ingest 认证:`X-Herald-Ingest-Key` → `hash_token()`(HMAC-SHA256,key=`SECRET_KEY`)→ 与 `ingest_endpoints.token_hash` 比较(`services/ingest.py:155-214`)。
- 渠道凭据以 Fernet 加密存 `channels.config_json_encrypted`(`backend/core/crypto.py` 的 `encrypt_json_bytes`/`decrypt_json_bytes`)。
- 前端经 `VITE_API_URL` 指向后端;auth 状态在 `frontend/src/lib/auth.tsx`(refresh token 存 sessionStorage,key `herald_refresh_token`)。
- 现有 edge 包(`edge/src/*.mjs`)是 Cloudflare "lite" 直发模式——**本计划整体删除重写**,其全部测试一并删除。
- CI(`.github/workflows/ci.yml`)已起 postgres:16-alpine 服务(`DATABASE_URL=postgresql://herald:herald@127.0.0.1:5432/herald`)。
- 文档守卫:`docs/AGENTS.md:68`、`docs/02_architecture.md:95` 写着"不得把 EdgeOne/代理模式写成现有功能"——**这是过时守卫,Task 19 删除;执行本计划即是在实现 EdgeOne 支持,两者不冲突。**

**平台事实**(已调研,不要重新怀疑;细节见设计文档 §0.5):CF 免费层 DO(SQLite+alarm)可用;EdgeOne 无 cron、Pages KV 无外部写 API、KV key 字符集仅 `[0-9A-Za-z_]`、CN 节点需 ICP 备案域名。

**里程碑**:M1 后端(Task 1–10)→ M2 Cloudflare 中继(Task 11–13)→ M3 EdgeOne 中继(Task 14–15)→ M4 运维/前端/文档(Task 16–20)。M1 完成后后端可独立部署;M2/M3 各自可独立验收。

---

### Task 0: 基线与分支

**Files:** 无代码改动。

- [ ] **Step 1:** 通读 `docs/12_production_upgrade_design.md` 全文。
- [ ] **Step 2:** 建分支:`git checkout -b production-upgrade`
- [ ] **Step 3:** 本地起测试数据库(与 CI 同参):
```bash
docker run -d --name herald-test-pg -e POSTGRES_DB=herald -e POSTGRES_USER=herald -e POSTGRES_PASSWORD=herald -p 5432:5432 postgres:16-alpine
```
- [ ] **Step 4:** 基线验证:`uv sync --project backend --locked && uv run --project backend --locked pytest backend/tests -v` 应全绿(现有后端测试不依赖 DB)。`npm --prefix edge ci && npm --prefix edge test` 全绿。记录两套实际通过数,后续任务用于对照(不要预设具体个数)。

---

## M1 后端

### Task 1: 迁移运行器 + 初始 schema

**Files:**
- Create: `backend/migrations/0001_initial.sql`
- Create: `backend/migrate.py`
- Create: `backend/tests/test_migrate.py`
- Delete: `backend/bootstrap_dev_db.py`
- Modify: `.github/workflows/ci.yml:70`(bootstrap 步骤 → migrate)

**Interfaces:**
- Produces: `apply_migrations(database_url: str) -> list[str]`(返回本次新应用的版本名);CLI `python -m backend.migrate`。后续所有任务假定该 schema(表名 `users/refresh_tokens/ingest_endpoints/channels/rules/messages/deliveries`)。

- [ ] **Step 1:** 写 `backend/migrations/0001_initial.sql`(完整内容):

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    family_id UUID NOT NULL,
    replaced_by_id UUID NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    last_used_at TIMESTAMPTZ NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ NULL,
    revoked_reason TEXT NULL,
    ip TEXT NULL,
    user_agent TEXT NULL
);
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens (user_id);
CREATE INDEX idx_refresh_tokens_family ON refresh_tokens (family_id);

CREATE TABLE ingest_endpoints (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    key_sha256 TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ NULL,
    deleted_at TIMESTAMPTZ NULL,
    last_used_at TIMESTAMPTZ NULL
);
CREATE INDEX idx_ingest_endpoints_user_created ON ingest_endpoints (user_id, created_at DESC);

CREATE TABLE channels (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    config_json_encrypted TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    disabled_at TIMESTAMPTZ NULL
);
CREATE INDEX idx_channels_user_created ON channels (user_id, created_at DESC);

CREATE TABLE rules (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    filter_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    payload_template_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_rules_user_created ON rules (user_id, created_at DESC);

CREATE TABLE messages (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ingest_endpoint_id UUID NOT NULL REFERENCES ingest_endpoints(id) ON DELETE CASCADE,
    received_at TIMESTAMPTZ NOT NULL,
    title TEXT NULL,
    body TEXT NOT NULL,
    "group" TEXT NULL,
    priority INTEGER NOT NULL DEFAULT 3,
    tags_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    url TEXT NULL,
    extras_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_type TEXT NULL,
    body_sha256 TEXT NOT NULL,
    headers_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    query_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    remote_ip TEXT NULL,
    user_agent TEXT NULL,
    relay_via TEXT NULL,
    deleted_at TIMESTAMPTZ NULL
);
CREATE INDEX idx_messages_user_received ON messages (user_id, received_at DESC);
CREATE INDEX idx_messages_endpoint ON messages (ingest_endpoint_id);

CREATE TABLE deliveries (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    rule_id UUID NOT NULL REFERENCES rules(id) ON DELETE CASCADE,
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NULL,
    sent_at TIMESTAMPTZ NULL,
    last_error TEXT NULL,
    provider_response_json JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_deliveries_message_status ON deliveries (message_id, status);
CREATE INDEX idx_deliveries_next_attempt ON deliveries (status, next_attempt_at);
```

(相对旧 schema 的全部差异:表名去前缀;删 `accounts_emailverificationtoken`、`accounts_passwordresettoken` 两表;`users` 删 `email_verified_at/is_staff/is_superuser`;`ingest_endpoints` 增 `key_sha256`;`messages` 增 `relay_via`。)

- [ ] **Step 2:** 写 `backend/migrate.py`(完整内容):

```python
"""Numbered SQL migration runner.

Usage: python -m backend.migrate
Files: backend/migrations/NNNN_name.sql, applied in filename order,
each inside one transaction, recorded in schema_migrations.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import asyncpg

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


async def apply_migrations(database_url: str) -> list[str]:
    conn = await asyncpg.connect(database_url)
    applied: list[str] = []
    try:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, "
            "applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        rows = await conn.fetch("SELECT version FROM schema_migrations")
        done = {row["version"] for row in rows}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = path.stem
            if version in done:
                continue
            async with conn.transaction():
                await conn.execute(path.read_text(encoding="utf-8"))
                await conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES ($1)", version
                )
            applied.append(version)
    finally:
        await conn.close()
    return applied


def main() -> None:
    # read env directly: get_settings() eagerly derives the async URL and would
    # raise a misleading unsupported_database_scheme error on an empty DATABASE_URL
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        sys.exit("DATABASE_URL is required")
    applied = asyncio.run(apply_migrations(url))
    print(f"migrations applied: {applied if applied else 'none (up to date)'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3:** 写失败测试 `backend/tests/test_migrate.py`(完整内容;`TEST_DATABASE_URL` 引自 conftest):

```python
import asyncio

import asyncpg
import pytest

from backend.migrate import apply_migrations
from backend.tests.conftest import TEST_DATABASE_URL


async def _fetchval(query: str):
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        return await conn.fetchval(query)
    finally:
        await conn.close()


async def _drop_all():
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    finally:
        await conn.close()


def test_apply_migrations_from_scratch_then_idempotent():
    asyncio.run(_drop_all())
    first = asyncio.run(apply_migrations(TEST_DATABASE_URL))
    assert first == ["0001_initial"]
    # tables exist
    n = asyncio.run(_fetchval(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name IN "
        "('users','refresh_tokens','ingest_endpoints','channels','rules','messages','deliveries')"
    ))
    assert n == 7
    # second run is a no-op
    second = asyncio.run(apply_migrations(TEST_DATABASE_URL))
    assert second == []
```

- [ ] **Step 4:** 跑 `uv run --project backend --locked pytest backend/tests/test_migrate.py -v` → 先失败(模块不存在)→ 落盘 Step 1/2 代码 → 通过。
- [ ] **Step 5:** `git rm backend/bootstrap_dev_db.py`。修改 `.github/workflows/ci.yml` 的 bootstrap 步骤(第 68–70 行附近):

```yaml
      - name: Apply database migrations
        run: uv run --project backend --locked python -m backend.migrate
```

- [ ] **Step 6:** 提交:`git commit -m "feat(backend): numbered SQL migrations, clean schema, drop bootstrap script"`

> 注:删除 bootstrap 后,`start.sh`(Task 16)与文档(Task 19)才改引用;在那之前 `./start.sh` 暂时不可用,属预期。

### Task 2: config 重构 + observability + 生产守卫

**Files:**
- Modify: `backend/config.py`
- Create: `backend/observability.py`
- Modify: `backend/app.py:66-76`(Sentry 初始化改调 observability)
- Modify: `backend/auth/tokens.py`(删 `TOKEN_HASH_KEY` 旁路与 `generate_token` 别名,新增 `sha256_hex`)
- Modify: `backend/auth/sessions.py`(`generate_token` → `generate_secret_token`,4 处调用:L24, L33, L70, L117)
- Test: `backend/tests/test_config.py`(新建)

**Interfaces:**
- Produces(后续任务全部依赖):`Settings` 新字段 `app_env: str`("development"|"production")、`edge_sync_token: str`(默认 "")、`forwarded_allow_ips: str`(默认 "")、`rate_limit_ingest_per_minute: int`(默认 120)、`rate_limit_auth_per_minute: int`(默认 10);`secret_key` 改读 env `SECRET_KEY`。`observability.init_sentry(*, extra_integrations: tuple = ()) -> None`。`auth/tokens.py` 新增 `sha256_hex(raw: str) -> str`。

- [ ] **Step 1:** 失败测试 `backend/tests/test_config.py`(完整内容):

```python
import pytest

from backend.config import get_settings


def _clear():
    get_settings.cache_clear()


def test_secret_key_env_var_renamed(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s3cret-value-0123456789abcdef")
    _clear()
    assert get_settings().secret_key == "s3cret-value-0123456789abcdef"
    _clear()


def test_production_rejects_default_secret_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    _clear()
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        get_settings()
    _clear()


def test_production_rejects_empty_encryption_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "s3cret-value-0123456789abcdef")
    monkeypatch.setenv("CHANNEL_CONFIG_ENCRYPTION_KEY", "")
    _clear()
    with pytest.raises(RuntimeError, match="CHANNEL_CONFIG_ENCRYPTION_KEY"):
        get_settings()
    _clear()


def test_production_rejects_empty_jwt_key_via_fallback(monkeypatch):
    # JWT_SIGNING_KEY set-but-empty must fall back to SECRET_KEY, not sign with ""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "s3cret-value-0123456789abcdef")
    monkeypatch.setenv("CHANNEL_CONFIG_ENCRYPTION_KEY", "dKkPUi_l6pJiD24yQWhv14jArlTc95xJMu38xpv8uKc=")
    monkeypatch.setenv("JWT_SIGNING_KEY", "")
    _clear()
    assert get_settings().jwt_signing_key == "s3cret-value-0123456789abcdef"
    _clear()


def test_development_accepts_defaults(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    _clear()
    assert get_settings().secret_key == "dev-insecure"
    _clear()
```

(conftest 的 autouse fixture 会设 `DATABASE_URL` 等,见 Task 3;本任务阶段沿用现 conftest,额外在本文件顶部无须处理。)

- [ ] **Step 2:** 修改 `backend/config.py`:
  - `Settings` dataclass 增字段:`app_env: str`、`edge_sync_token: str`、`forwarded_allow_ips: str`、`rate_limit_ingest_per_minute: int`、`rate_limit_auth_per_minute: int`。
  - `get_settings()` 内(现 L90–128 区域):

```python
    app_env = _env_str("APP_ENV", "development").lower()
    secret_key = os.environ.get("SECRET_KEY", "dev-insecure")
    channel_config_encryption_key = os.environ.get("CHANNEL_CONFIG_ENCRYPTION_KEY", "")
    # `or`(而非 get 的 default)让"设了但为空串"也回落 SECRET_KEY —— compose 传空值时不会用空密钥签 JWT
    jwt_signing_key = os.environ.get("JWT_SIGNING_KEY") or secret_key

    if app_env == "production":
        problems = []
        if secret_key in ("", "dev-insecure"):
            problems.append("SECRET_KEY must be set to a strong value")
        if jwt_signing_key == "dev-insecure":
            problems.append("JWT_SIGNING_KEY must not be a default value")
        if not channel_config_encryption_key:
            problems.append("CHANNEL_CONFIG_ENCRYPTION_KEY must be set")
        if problems:
            raise RuntimeError("refusing to start in production: " + "; ".join(problems))
```

  - 新增 `def _env_float(key: str, default: float) -> float`(仿 `_env_int`,解析失败回默认),`worker_poll_seconds` 与 `sentry_traces_sample_rate` 改用它(替换现有裸 `float()`)。
  - 其余新字段:`edge_sync_token=os.environ.get("EDGE_SYNC_TOKEN", "")`、`forwarded_allow_ips=_env_str("FORWARDED_ALLOW_IPS", "")`、`rate_limit_ingest_per_minute=_env_int("RATE_LIMIT_INGEST_PER_MINUTE", 120)`、`rate_limit_auth_per_minute=_env_int("RATE_LIMIT_AUTH_PER_MINUTE", 10)`。
- [ ] **Step 3:** 写 `backend/observability.py`(完整内容):

```python
"""Shared Sentry initialization for API and worker processes."""

from __future__ import annotations

from .config import get_settings


def init_sentry(*, extra_integrations: tuple = ()) -> None:
    settings = get_settings()
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=list(extra_integrations),
        traces_sample_rate=settings.sentry_traces_sample_rate,
        environment=settings.sentry_environment,
    )
```

- [ ] **Step 4:** `backend/app.py` 的 Sentry 块(L66–76)替换为:

```python
    from .observability import init_sentry

    try:
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        init_sentry(extra_integrations=(StarletteIntegration(), FastApiIntegration()))
    except ImportError:
        pass
```

- [ ] **Step 5:** `backend/auth/tokens.py`:删除 `TOKEN_HASH_KEY` 环境变量旁路(`hash_token` 的 key 一律 `get_settings().secret_key`)。别名 `generate_token = generate_secret_token` **有活跃调用方**(`backend/auth/sessions.py` L24/L33/L70/L117)——先把 sessions.py 的 import 与 4 处调用改为 `generate_secret_token`,再删别名。新增:

```python
def sha256_hex(raw_token: str) -> str:
    """Unkeyed SHA-256 hex digest — the edge-relay offline verifier."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
```

- [ ] **Step 6:** 全库替换 env 名:`grep -rn "DJANGO_SECRET_KEY" --include="*.py" --include="*.yml" --include="*.yaml" --include="*.sh" .` → 逐处改为 `SECRET_KEY`(conftest、docker-compose、ci.yml、start.sh;compose/start.sh 的完整改造在 Task 16,此处仅改名保持可运行)。
- [ ] **Step 7:** 跑 `pytest backend/tests/test_config.py -v` 通过;全套 `pytest backend/tests -v` 通过。提交:`git commit -m "feat(backend): APP_ENV production guard, SECRET_KEY rename, shared sentry init"`

### Task 3: 测试地基(conftest 真库 fixtures + 工厂)

**Files:**
- Modify: `backend/tests/conftest.py`(整体重写)
- Modify: `backend/database.py`(反射表名改为新 schema;删两张 token 表字段)

**Interfaces:**
- Produces(后续测试任务全部消费):`TEST_DATABASE_URL`;fixture `app`;同步 SQL 助手 `_run_sql(query, *args)`(可从任意测试 import,**在同步与 async 测试体内都安全**);同步工厂 `make_user(email, password) -> dict`、`make_ingest_endpoint(user_id) -> dict`(含 `raw_key`)、`make_channel(user_id, type_, config) -> dict`、`make_rule(user_id, channel_id, filter_json=None, payload_template=None) -> dict`。所有工厂直接 SQL 插入(不依赖 service 层命名),返回含 `id` 的 dict。测试内的 HTTP 客户端各文件自行 `AsyncClient(transport=ASGITransport(app=app), ...)` 构造,不设共享 fixture。

- [ ] **Step 1:** 修改 `backend/database.py`:`ReflectedTables` 删 `email_verification_tokens`、`password_reset_tokens` 字段;反射名单(L91–101)改为 `users, ingest_endpoints, channels, rules, messages, deliveries, refresh_tokens`(七张,新名)。
- [ ] **Step 2:** 重写 `backend/tests/conftest.py`(完整内容):

```python
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import asyncpg
import pytest

from backend.config import get_settings
from backend.database import clear_database_state
from backend.migrate import apply_migrations

TEST_DATABASE_URL = "postgresql://herald:herald@127.0.0.1:5432/herald"
TEST_JWT_SIGNING_KEY = "test-jwt-signing-key-0123456789abcdef"
TEST_SECRET_KEY = "test-secret-key-0123456789abcdef"
TEST_ENCRYPTION_KEY = "dKkPUi_l6pJiD24yQWhv14jArlTc95xJMu38xpv8uKc="

_ALL_TABLES = "users, refresh_tokens, ingest_endpoints, channels, rules, messages, deliveries"


@pytest.fixture(autouse=True)
def configure_backend_test_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET_KEY)
    monkeypatch.setenv("JWT_SIGNING_KEY", TEST_JWT_SIGNING_KEY)
    monkeypatch.setenv("CHANNEL_CONFIG_ENCRYPTION_KEY", TEST_ENCRYPTION_KEY)
    monkeypatch.setenv("DB_POOL_CLASS", "null")  # engines are re-created per test loop
    get_settings.cache_clear()
    clear_database_state()
    yield
    get_settings.cache_clear()
    clear_database_state()


@pytest.fixture(scope="session", autouse=True)
def _migrated_database():
    asyncio.run(apply_migrations(TEST_DATABASE_URL))
    yield


@pytest.fixture(autouse=True)
def _clean_tables(_migrated_database):
    asyncio.run(_truncate_all())  # before each test: immune to dirt from prior runs
    yield


async def _truncate_all() -> None:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await conn.execute(f"TRUNCATE {_ALL_TABLES} CASCADE")
    finally:
        await conn.close()


def _run_sql(query: str, *args):
    """Loop-safe sync SQL helper: usable from sync fixtures AND inside
    @pytest.mark.asyncio test bodies (asyncio.run would raise there)."""

    async def _go():
        conn = await asyncpg.connect(TEST_DATABASE_URL)
        try:
            return await conn.fetchrow(query, *args)
        finally:
            await conn.close()

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_go())
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _go()).result()


@pytest.fixture
def app(configure_backend_test_env):
    from backend.app import create_app

    return create_app()


@pytest.fixture
def make_user(configure_backend_test_env):
    from backend.auth.passwords import make_password

    def _make(email: str = "u@example.com", password: str = "pw-123456") -> dict:
        user_id = uuid.uuid4()
        _run_sql(
            "INSERT INTO users (id, email, password, is_active, created_at) "
            "VALUES ($1, $2, $3, TRUE, $4)",
            user_id, email, make_password(password), datetime.now(timezone.utc),
        )
        return {"id": user_id, "email": email, "password": password}

    return _make


@pytest.fixture
def make_ingest_endpoint(configure_backend_test_env):
    from backend.auth.tokens import generate_secret_token, hash_token, sha256_hex

    def _make(user_id, name: str = "ep") -> dict:
        endpoint_id = uuid.uuid4()
        raw_key = generate_secret_token(32)
        _run_sql(
            "INSERT INTO ingest_endpoints (id, user_id, name, token_hash, key_sha256, created_at) "
            "VALUES ($1, $2, $3, $4, $5, $6)",
            endpoint_id, user_id, name, hash_token(raw_key), sha256_hex(raw_key),
            datetime.now(timezone.utc),
        )
        return {"id": endpoint_id, "raw_key": raw_key, "name": name}

    return _make


@pytest.fixture
def make_channel(configure_backend_test_env):
    import json as _json

    from backend.core.crypto import encrypt_json_bytes

    def _make(user_id, type_: str = "ntfy",
              config: dict | None = None, name: str = "ch") -> dict:
        channel_id = uuid.uuid4()
        cfg = config or {"server_base_url": "https://ntfy.example.com", "topic": "t"}
        _run_sql(
            "INSERT INTO channels (id, user_id, type, name, config_json_encrypted, created_at) "
            "VALUES ($1, $2, $3, $4, $5, $6)",
            channel_id, user_id, type_, name,
            encrypt_json_bytes(_json.dumps(cfg).encode("utf-8")),
            datetime.now(timezone.utc),
        )
        return {"id": channel_id, "type": type_, "config": cfg}

    return _make


@pytest.fixture
def make_rule(configure_backend_test_env):
    import json as _json

    def _make(user_id, channel_id, filter_json: dict | None = None,
              payload_template: dict | None = None, enabled: bool = True) -> dict:
        rule_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        _run_sql(
            "INSERT INTO rules (id, user_id, name, enabled, filter_json, channel_id, "
            "payload_template_json, created_at, updated_at) "
            "VALUES ($1, $2, 'r', $3, $4, $5, $6, $7, $7)",
            rule_id, user_id, enabled, _json.dumps(filter_json or {}),
            channel_id, _json.dumps(payload_template or {}), now,
        )
        return {"id": rule_id, "channel_id": channel_id}

    return _make
```

> 注意:`encrypt_json_bytes` 的准确签名以 `backend/core/crypto.py` 现文件为准(生产代码在 `worker.py:166-171` 用 `decrypt_json_bytes` 解密 `config_json_encrypted` 列);若签名不符,以生产调用方式对齐工厂实现。

- [ ] **Step 3:** 跑全套 `pytest backend/tests -v`。现存 `test_routes.py` 的 health 测试因真库存在应稳定返回 200。修掉任何因表名反射变化而失败的现存测试(此时 services 仍引用旧 `tables.xxx` 属性名——`ReflectedTables` 字段名未变,只有底层表名变,服务层代码无需改动)。
- [ ] **Step 4:** 提交:`git commit -m "test(backend): real-database fixtures, factories, new schema reflection"`

### Task 4: auth 收敛(删邮件装置、合并文件、CLI 重置、前端同步)

**Files:**
- Delete: `backend/routes/auth_token_routes.py`、`backend/services/auth_tokens.py`
- Create: `backend/routes/auth.py`(重写,吸收 `auth_account_routes.py` + `auth_session_routes.py` + `auth_common.py`,三者删除)
- Create: `backend/services/auth.py`(吸收 `auth_accounts.py`、`auth_sessions.py`、`auth_shared.py`、`auth_users.py`,四者删除)
- Modify: `backend/auth/jwt.py`(删 L59–85 `get_verified_user_id`)
- Modify: `backend/schemas/auth.py`(删 `VerifyEmailRequest`/`ForgotPasswordRequest`/`ResetPasswordRequest`;`UserResponse`/user dict 删 `email_verified_at`)
- Modify: `backend/services/ingest.py:194-209`(删 `email_not_verified` 门禁,保留 `is_active` 检查)
- Modify: `backend/cli.py`(新增 `reset-password` 子命令)
- Modify: `backend/routes/__init__.py`(auth 路由 import 对齐)
- Test: `backend/tests/test_auth_flows.py`(新建);`backend/tests/test_auth.py` 保留(纯 JWT)

(前端对应删改**全部放在 Task 18**,本任务只动 backend——期间前端的 verify/reset 页面调用已删端点会得到 404,不影响构建。)

**Interfaces:**
- Produces:`backend/services/auth.py` 保留被合并模块的**原函数名与签名**(机械搬运,不重命名)。八个端点:`POST /api/auth/{signup,login,refresh,logout,change-email,change-password,delete-account}`、`GET /api/auth/me`。CLI:`herald-backend reset-password <email>`。
- 响应形状不变(机械搬运的推论):`/me`、`/signup`、`/change-email` 返回 `UserResponse` 的 **`{"user": {...}}` 包裹形状**(`backend/schemas/auth.py:19-20`),仅删除 user 对象里的 `email_verified_at` 字段;login/refresh 返回 `AuthSessionResponse` 现有字段。测试断言以这些现有 schema 为准。
- 删除的端点:`/api/auth/verify-email`、`/api/auth/forgot-password`、`/api/auth/reset-password`、`/api/auth/resend-verification`。

- [ ] **Step 1:** 失败测试 `backend/tests/test_auth_flows.py`(完整内容):

```python
import pytest
from httpx import ASGITransport, AsyncClient


async def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_signup_login_me_roundtrip(app):
    async with await _client(app) as c:
        r = await c.post("/api/auth/signup", json={"email": "a@x.com", "password": "pw-123456"})
        assert r.status_code == 201
        r = await c.post("/api/auth/login", json={"email": "a@x.com", "password": "pw-123456"})
        assert r.status_code == 200
        body = r.json()
        assert body["access_token"] and body["refresh_token"]
        r = await c.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
        assert r.status_code == 200
        assert r.json()["user"]["email"] == "a@x.com"
        assert "email_verified_at" not in r.json()["user"]


@pytest.mark.asyncio
async def test_refresh_rotation_and_reuse_detection(app):
    async with await _client(app) as c:
        await c.post("/api/auth/signup", json={"email": "b@x.com", "password": "pw-123456"})
        login = (await c.post("/api/auth/login", json={"email": "b@x.com", "password": "pw-123456"})).json()
        old_refresh = login["refresh_token"]
        r1 = await c.post("/api/auth/refresh", json={"refresh_token": old_refresh})
        assert r1.status_code == 200
        new_refresh = r1.json()["refresh_token"]
        assert new_refresh != old_refresh
        # replaying the rotated-out token trips family compromise
        r2 = await c.post("/api/auth/refresh", json={"refresh_token": old_refresh})
        assert r2.status_code == 401
        # the whole family is revoked, new token dead too
        r3 = await c.post("/api/auth/refresh", json={"refresh_token": new_refresh})
        assert r3.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_refresh(app):
    async with await _client(app) as c:
        await c.post("/api/auth/signup", json={"email": "c@x.com", "password": "pw-123456"})
        login = (await c.post("/api/auth/login", json={"email": "c@x.com", "password": "pw-123456"})).json()
        r = await c.post("/api/auth/logout", json={"refresh_token": login["refresh_token"]},
                         headers={"Authorization": f"Bearer {login['access_token']}"})
        assert r.status_code == 204
        r = await c.post("/api/auth/refresh", json={"refresh_token": login["refresh_token"]})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_change_password_revokes_all_sessions(app):
    async with await _client(app) as c:
        await c.post("/api/auth/signup", json={"email": "d@x.com", "password": "pw-123456"})
        login = (await c.post("/api/auth/login", json={"email": "d@x.com", "password": "pw-123456"})).json()
        r = await c.post(
            "/api/auth/change-password",
            json={"current_password": "pw-123456", "new_password": "pw-654321"},
            headers={"Authorization": f"Bearer {login['access_token']}"},
        )
        assert r.status_code == 204
        r = await c.post("/api/auth/refresh", json={"refresh_token": login["refresh_token"]})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_dead_mailer_endpoints_are_gone(app):
    async with await _client(app) as c:
        for path in ("/api/auth/verify-email", "/api/auth/forgot-password",
                     "/api/auth/reset-password", "/api/auth/resend-verification"):
            r = await c.post(path, json={})
            assert r.status_code == 404, path
```

(login/refresh/logout 的请求/响应字段名以 `backend/schemas/auth.py` 现有 `LoginRequest`/`RefreshRequest`/`LogoutRequest`/`AuthSessionResponse` 为准——若字段名与上文不符,按 schema 修正测试,不改 schema。)

- [ ] **Step 2:** 合并 service:新建 `backend/services/auth.py`,按下表机械搬运(源文件行号为现状,搬完删源文件):

| 来源 | 函数 |
|---|---|
| `services/auth_shared.py` | 全部 3 个 helper(`build_user_dict` 删掉 `email_verified_at` 字段) |
| `services/auth_users.py` | 唯一函数 |
| `services/auth_accounts.py` | signup/change-email/change-password/delete-account 相关全部;signup 中删除 `email_verified_at=None`、`is_staff=False`、`is_superuser=False` 三个列写入(新 `users` 表无这些列);change-email 中删除 `email_verified_at=None` 写入(auth_accounts.py:79) |
| `services/auth_sessions.py` | login/refresh/logout 全部 |

- [ ] **Step 3:** 合并 route:重写 `backend/routes/auth.py` 为单文件八端点(搬运 `auth_account_routes.py`(去掉 `/resend-verification`)与 `auth_session_routes.py` 的 handler,`auth_common.py` 的共享依赖一并搬入),`router = APIRouter(prefix="/api/auth", tags=["auth"])`。删除四个旧文件与 `routes/__init__.py` 里对它们的 import。
- [ ] **Step 4:** 改 `services/ingest.py` 的 L194–209 整块:用户查询里**同时删除** `tables.users.c.email_verified_at` 的 select 列(L194–197,新表没有该列,留着会 AttributeError)与 `email_not_verified` 403 分支(L204–208),仅保留 `is_active` 检查与 403。删 `auth/jwt.py:59-85`。schema 清理如 Files 所列。
- [ ] **Step 5:** `backend/cli.py` 增子命令(argparse 改造:无子命令 = 起服务,保持 `herald-backend` 现行为):

```python
def _reset_password(email: str) -> None:
    import asyncio
    import secrets

    import asyncpg

    from .auth.passwords import make_password
    from .config import get_settings

    new_password = secrets.token_urlsafe(12)

    async def _go() -> int:
        conn = await asyncpg.connect(get_settings().raw_database_url)
        try:
            result = await conn.execute(
                "UPDATE users SET password = $1 WHERE email = $2",
                make_password(new_password), email,
            )
            return int(result.split()[-1])
        finally:
            await conn.close()

    if asyncio.run(_go()) == 0:
        raise SystemExit(f"no user with email {email}")
    print(f"new password for {email}: {new_password}")
```

`main()`:`subparsers = parser.add_subparsers(dest="command")`;`serve`(默认,现 uvicorn 逻辑)与 `reset-password <email>`。
- [ ] **Step 6:** `pytest backend/tests -v` 全绿(含新 flows);grep 验证:`grep -rn "email_verified\|verify-email\|forgot-password\|reset-password\|resend-verification" backend/ --include="*.py"` 命中仅剩两类:CLI 的 `reset-password` 子命令,与 `backend/tests/test_auth_flows.py` 里断言死端点 404 的字符串字面量(这些命中是预期,不要"修掉")。
- [ ] **Step 7:** 提交:`git commit -m "feat(auth): remove dead mailer flows, consolidate auth into two files, CLI password reset"`

### Task 5: 删除垫片与死代码

**Files:**
- Delete: `backend/models.py`、`backend/requests.py`
- Modify: `backend/services/__init__.py`(清空为空文件)、`backend/schemas/__init__.py`(只保留仍被 ≥2 处 import 的 re-export,否则清空)、`backend/core/crypto.py`(删 L21–29 `encrypt_config`/`decrypt_config`)
- Modify: 所有 importer(机械改 import 路径)

- [ ] **Step 1:** `grep -rln "from backend.models\|from .models\|from ..models\|from backend.requests\|from .requests\|from ..requests" backend/` 列出全部消费者;逐个把 import 改为 `from ..schemas.xxx import Yyy` 直连。
- [ ] **Step 2:** 清空 `services/__init__.py`(brief 确认生产零消费者,仅 3 个测试文件用到——改那 3 个测试的 import)。
- [ ] **Step 3:** `core/crypto.py` 删 `encrypt_config`/`decrypt_config`;`tests/test_core.py` 的 `TestCrypto` 改测 `encrypt_json_bytes`/`decrypt_json_bytes`(生产真实使用的函数,worker.py:166-171 消费)。
- [ ] **Step 4:** `pytest backend/tests -v` 全绿;`git rm backend/models.py backend/requests.py`;提交 `git commit -m "refactor(backend): delete re-export shims and dead crypto wrappers"`

### Task 6: CORS 替换 + 限流中间件 + 代理头

**Files:**
- Modify: `backend/middleware.py`(删 `CorsMiddleware` L33–104、`_set_cors_headers` L90–104、自制 `MutableHeaders` 类 L184–199——**注意** `RequestIDMiddleware` 在 L127 使用它,须同时把该处改为 `from starlette.datastructures import MutableHeaders`,其构造同样接受 `scope=message` 并原位改写 headers 列表;新增 `RateLimitMiddleware`;模块 docstring 保留"禁 BaseHTTPMiddleware"说明)
- Modify: `backend/app.py:83-85`(中间件注册)
- Modify: `backend/cli.py`(uvicorn 代理头)
- Test: `backend/tests/test_middleware.py`(增限流用例;删 L38–45 无断言测试)

**Interfaces:**
- Produces:`RateLimitMiddleware(app)`——纯 ASGI;`POST /api/ingest/{id}` 按 endpoint id 桶、`/api/auth/login|signup|refresh` 按客户端 IP 桶;超限 429 `{"detail":"rate_limited"}` + `Retry-After: 60`。

- [ ] **Step 1:** 失败测试(追加到 `test_middleware.py`;同时删除 `test_health_not_access_logged`):

```python
@pytest.mark.asyncio
async def test_auth_rate_limit_returns_429(app, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MINUTE", "3")
    from backend.config import get_settings
    get_settings.cache_clear()
    from backend.app import create_app
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        statuses = []
        for _ in range(5):
            r = await c.post("/api/auth/login", json={"email": "x@x.com", "password": "wrong"})
            statuses.append(r.status_code)
    assert 429 in statuses
    assert statuses[0] != 429
```

- [ ] **Step 2:** 实现 `RateLimitMiddleware`(加入 `backend/middleware.py`,完整内容;依赖的 `time`、`Response`、`ASGIApp/Scope/Receive/Send` 类型别名与 `get_settings` 在现文件顶部均已 import——删除 CorsMiddleware 时**保留**这些 import):

```python
class RateLimitMiddleware:
    """In-process token buckets. Single-instance deployment only.

    ponytail: per-process buckets; move to a shared store if this ever runs >1 replica.
    """

    _AUTH_PATHS = {"/api/auth/login", "/api/auth/signup", "/api/auth/refresh"}

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_ts)

    def _match(self, scope: Scope) -> tuple[str, int] | None:
        if scope.get("method") != "POST":
            return None
        path = scope.get("path", "")
        settings = get_settings()
        if path.startswith("/api/ingest/"):
            return (f"ingest:{path.rsplit('/', 1)[-1]}", settings.rate_limit_ingest_per_minute)
        if path in self._AUTH_PATHS:
            client = scope.get("client") or ("", 0)
            return (f"auth:{client[0]}", settings.rate_limit_auth_per_minute)
        return None

    def _allow(self, key: str, per_minute: int) -> bool:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (float(per_minute), now))
        tokens = min(float(per_minute), tokens + (now - last) * per_minute / 60.0)
        if tokens < 1.0:
            self._buckets[key] = (tokens, now)
            return False
        if len(self._buckets) > 10_000:
            self._buckets.clear()  # ponytail: crude flush beats an LRU nobody needs
        self._buckets[key] = (tokens - 1.0, now)
        return True

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        matched = self._match(scope)
        if matched and not self._allow(*matched):
            response = Response(
                content=b'{"detail":"rate_limited"}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60"},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
```

- [ ] **Step 3:** `app.py` 注册改为(注意 add_middleware 前插,运行序 = 注册逆序;CORS 必须**最后注册**使其成为最外层——否则限流的 429 缺 CORS 头,浏览器只见不透明网络错误):

```python
    from starlette.middleware.cors import CORSMiddleware

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Herald-Ingest-Key"],
        max_age=600,
    )
```

(运行序变为 CORS → RequestID → AccessLog → RateLimit → app;access log 仍带 request_id——RequestID 在其外层。)

- [ ] **Step 4:** `cli.py` 的 uvicorn 调用加:`proxy_headers=True, forwarded_allow_ips=get_settings().forwarded_allow_ips or None`。
- [ ] **Step 5:** `pytest backend/tests -v` 全绿。提交:`git commit -m "feat(backend): starlette CORS, in-process rate limiting, trusted proxy headers"`

### Task 7: 渠道配置 Pydantic 化

**Files:**
- Create: `backend/schemas/channel_configs.py`
- Delete: `backend/services/channel_validation.py`
- Modify: `backend/services/channel_operations.py`(调用点换新函数)
- Test: `backend/tests/test_channel_configs.py`(承接并替换 `test_services.py`,后者删除)

**Interfaces:**
- Produces:`normalize_channel_config(channel_type: str, config: object) -> dict` 与 `SUPPORTED_CHANNEL_TYPES`;校验失败抛现有 `services.exceptions.ChannelConfigValidationError`,`.details` 为 pydantic `errors()` 的 `loc` 直接扁平化:`{"config": {<loc首段或 non_field_errors>: [消息]}}`。**不保留** DRF 文案与旧字段归属(核实过:前端只渲染 `error.message`,无代码消费字段级结构)。field validator 的错误自然归属该字段;model validator(跨字段规则)归 `non_field_errors`,消息文本自说明。

- [ ] **Step 1:** 把 `test_services.py` 的 9 个 Gotify 用例搬到 `test_channel_configs.py`(import 换 `from backend.schemas.channel_configs import normalize_channel_config`;涉及错误字段归属的断言按新规则调整:`server_base_url`/`app_token`/`default_priority` 等字段级错误仍落在 `details["config"]["<field>"]`,跨字段错误落在 `details["config"]["non_field_errors"]`,错误文案以消息内容判断而非精确匹配 DRF 原文),另补 bark(device_key 从 URL 提取、两者皆缺报错)、ntfy(双认证冲突报错)、mqtt(私网 host 拒绝)各 2–3 个用例。跑之,失败。
- [ ] **Step 2:** 实现 `backend/schemas/channel_configs.py`(完整内容):

```python
"""Channel config validation as Pydantic models (replaces the hand-rolled framework)."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from ..core.ssrf import assert_host_ssrf_safe, assert_ssrf_safe
from ..services.exceptions import ChannelConfigValidationError

CHANNEL_TYPE_BARK = "bark"
CHANNEL_TYPE_NTFY = "ntfy"
CHANNEL_TYPE_MQTT = "mqtt"
CHANNEL_TYPE_GOTIFY = "gotify"
SUPPORTED_CHANNEL_TYPES = (CHANNEL_TYPE_BARK, CHANNEL_TYPE_NTFY, CHANNEL_TYPE_MQTT, CHANNEL_TYPE_GOTIFY)


def _looks_like_device_key(segment: str) -> bool:
    return (
        len(segment) >= 16
        and any(ch.isdigit() for ch in segment)
        and all(ch.isalnum() or ch in "_-" for ch in segment)
    )


class _Config(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class BarkConfig(_Config):
    server_base_url: str
    device_key: str | None = None
    device_keys: list[str] | None = None
    default_payload_json: dict | None = None

    @model_validator(mode="after")
    def _normalize(self) -> "BarkConfig":
        base = self.server_base_url.rstrip("/")
        if base.endswith("/push"):
            base = base[: -len("/push")].rstrip("/")
        if not self.device_key and not self.device_keys:
            parsed = urlparse(base)
            segments = [s for s in parsed.path.split("/") if s]
            if len(segments) == 1 and _looks_like_device_key(segments[0]):
                self.device_key = segments[0]
                base = f"{parsed.scheme}://{parsed.netloc}"
            else:
                raise ValueError("device_key is required (or set device_keys)")
        self.server_base_url = base
        assert_ssrf_safe(base)
        return self


class NtfyConfig(_Config):
    server_base_url: str
    topic: str
    access_token: str | None = None
    username: str | None = None
    password: str | None = None
    default_headers_json: dict | None = None

    @model_validator(mode="after")
    def _check_auth(self) -> "NtfyConfig":
        if self.access_token and (self.username or self.password):
            raise ValueError("choose one auth method: access_token or username/password")
        if bool(self.username) != bool(self.password):
            raise ValueError("username and password must be set together")
        self.server_base_url = self.server_base_url.rstrip("/")
        assert_ssrf_safe(f"{self.server_base_url}/{self.topic}")
        return self


class MqttConfig(_Config):
    broker_host: str
    topic: str
    broker_port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = None
    password: str | None = None
    tls: bool | None = None
    tls_insecure: bool | None = None
    qos: int | None = Field(default=None, ge=0, le=2)
    retain: bool | None = None
    client_id: str | None = None
    keepalive_seconds: int | None = Field(default=None, ge=1, le=3600)

    @model_validator(mode="after")
    def _check(self) -> "MqttConfig":
        if bool(self.username) != bool(self.password):
            raise ValueError("username and password must be set together")
        assert_host_ssrf_safe(self.broker_host, block_private_networks=True)
        return self


class GotifyConfig(_Config):
    server_base_url: str
    app_token: str
    default_priority: int | None = Field(default=None, ge=0, le=10)
    default_extras_json: dict | None = None
    default_payload_json: dict | None = None

    @field_validator("server_base_url")
    @classmethod
    def _check_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("must be an http(s) URL")
        v = v.rstrip("/")
        assert_ssrf_safe(v)
        return v


_MODELS: dict[str, type[_Config]] = {
    CHANNEL_TYPE_BARK: BarkConfig,
    CHANNEL_TYPE_NTFY: NtfyConfig,
    CHANNEL_TYPE_MQTT: MqttConfig,
    CHANNEL_TYPE_GOTIFY: GotifyConfig,
}


def normalize_channel_type(raw: object) -> str:
    value = str(raw or "").strip()
    if value not in _MODELS:
        raise ChannelConfigValidationError(details={"type": [f'"{value}" is not a valid choice.']})
    return value


def normalize_channel_config(channel_type: str, config: object) -> dict:
    if not isinstance(config, dict):
        raise ChannelConfigValidationError(details={"config": {"non_field_errors": ["Expected an object."]}})
    model = _MODELS[normalize_channel_type(channel_type)]
    try:
        validated = model.model_validate(config)
    except ValidationError as exc:
        # SSRFError subclasses ValueError, so pydantic folds SSRF failures into
        # ValidationError too — this single branch covers everything.
        details: dict[str, list[str]] = {}
        for err in exc.errors():
            field = str(err["loc"][0]) if err["loc"] else "non_field_errors"
            details.setdefault(field, []).append(err["msg"].removeprefix("Value error, "))
        raise ChannelConfigValidationError(details={"config": details}) from exc
    return validated.model_dump(exclude_none=True)
```

> `exclude_none=True` 保持"未提供的可选键不出现在存储配置里"的现语义(dispatch 层负责运行时默认值,见 `channel_dispatch.py:47-63`)。若现存测试断言可选键为 `None` 而非缺失,以 dispatch 的实际消费方式为准修正测试。

- [ ] **Step 3:** 改 `services/channel_operations.py` 调用点(**不是**纯机械换 import——当前 L14–17 引入的是 `_normalize_channel_config`(下划线名)与 `require_string_field`):
  - `_normalize_channel_config(...)` 调用(L87–89 附近)→ `normalize_channel_config(...)`,import 换 `from ..schemas.channel_configs import normalize_channel_config, normalize_channel_type, SUPPORTED_CHANNEL_TYPES`(按实际使用取舍)。
  - `require_string_field({"name": name}, "name")` 这类对渠道 `name` 的校验(name 不属于 config 模型)→ 内联:`if not isinstance(name, str) or not name.strip(): raise ChannelConfigValidationError(details={"name": ["This field is required."]})`,随后 `name = name.strip()`。
  - 然后 `git rm backend/services/channel_validation.py backend/tests/test_services.py`。
- [ ] **Step 4:** `pytest backend/tests -v` 全绿。提交:`git commit -m "refactor(channels): pydantic config models replace hand-rolled validation framework"`

### Task 8: ingest 幂等 + 中继头 + key_sha256

**Files:**
- Modify: `backend/services/ingest.py`(`create_ingest_message` 幂等化;签名扩展)
- Modify: `backend/routes/ingest.py`(读中继头;201/200 区分)
- Modify: `backend/services/ingest_endpoints.py:66-96`(创建时写 `key_sha256`)
- Modify: `backend/schemas/ingest.py`(`IngestMessageResponse` 增可选 `duplicate: bool = False`)
- Test: `backend/tests/test_ingest_api.py`(新建)

**Interfaces:**
- Produces:`create_ingest_message(..., message_id: uuid.UUID | None = None, received_at: datetime | None = None, relay_via: str | None = None) -> tuple[str, bool]`。**返回的 message_id 统一为带连字符的 UUID 字符串**(两条路径都过 `serialize_uuid`;现非重复路径返回 `uuid.UUID` 对象——必须转 str,否则 `JSONResponse` 序列化崩溃)。HTTP:新消息 201 `{"message_id": ...}`;重复 200 `{"message_id": ..., "duplicate": true}`。中继头仅认证通过后解析:`X-Herald-Message-Id` 非法 UUID → 422 `invalid_relay_message_id`;`X-Herald-Received-At` 非法或距今 >48h → 忽略(用服务器时间);`X-Herald-Relay-Via` 仅保留 `[a-z,]`,截断 64 字符。同时删除无文档的遗留别名路由 `POST /ingest/{endpoint_id}`(routes/ingest.py:35)——协议只有一个 ingest 面。

- [ ] **Step 1:** 失败测试 `backend/tests/test_ingest_api.py`(完整内容):

```python
import uuid

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def setup(make_user, make_ingest_endpoint):
    user = make_user()
    ep = make_ingest_endpoint(user["id"])
    return user, ep


def _url(ep):
    return f"/api/ingest/{ep['id'].hex}"


async def _post(app, ep, json_body=None, headers=None, raw=None):
    h = {"X-Herald-Ingest-Key": ep["raw_key"], "Content-Type": "application/json"}
    h.update(headers or {})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        if raw is not None:
            return await c.post(_url(ep), content=raw, headers=h)
        return await c.post(_url(ep), json=json_body, headers=h)


@pytest.mark.asyncio
async def test_wrong_key_401(app, setup):
    _, ep = setup
    r = await _post(app, {**ep, "raw_key": "wrong"}, {"body": "hi"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_happy_path_201_creates_delivery(app, setup, make_channel, make_rule):
    user, ep = setup
    ch = make_channel(user["id"])
    make_rule(user["id"], ch["id"])
    r = await _post(app, ep, {"body": "hello", "priority": 5})
    assert r.status_code == 201
    mid = r.json()["message_id"]
    from backend.tests.conftest import _run_sql
    row = _run_sql("SELECT count(*) AS n FROM deliveries WHERE message_id = $1", uuid.UUID(mid))
    assert row["n"] == 1


@pytest.mark.asyncio
async def test_validation_errors(app, setup):
    _, ep = setup
    assert (await _post(app, ep, {"body": "x", "bogus": 1})).status_code == 422
    assert (await _post(app, ep, {"title": "no body"})).status_code == 422
    assert (await _post(app, ep, raw=b"not json")).status_code == 400
    assert (await _post(app, ep, raw=b"x" * (1024 * 1024 + 1))).status_code == 413
    r = await _post(app, ep, raw=b"plain", headers={"Content-Type": "text/plain"})
    assert r.status_code == 415


@pytest.mark.asyncio
async def test_ingest_rate_limit_429(setup, monkeypatch):
    _, ep = setup
    monkeypatch.setenv("RATE_LIMIT_INGEST_PER_MINUTE", "2")
    from backend.config import get_settings
    get_settings.cache_clear()
    from backend.app import create_app
    app = create_app()
    statuses = [(await _post(app, ep, {"body": "x"})).status_code for _ in range(4)]
    assert statuses[0] in (201, 200) and 429 in statuses


@pytest.mark.asyncio
async def test_relay_idempotency(app, setup, make_channel, make_rule):
    user, ep = setup
    ch = make_channel(user["id"])
    make_rule(user["id"], ch["id"])
    mid = str(uuid.uuid4())
    relay = {"X-Herald-Message-Id": mid, "X-Herald-Relay-Via": "edgeone,cloudflare"}
    r1 = await _post(app, ep, {"body": "once"}, headers=relay)
    assert r1.status_code == 201
    assert r1.json()["message_id"].replace("-", "") == mid.replace("-", "")
    r2 = await _post(app, ep, {"body": "once"}, headers=relay)
    assert r2.status_code == 200
    assert r2.json()["duplicate"] is True
    from backend.tests.conftest import _run_sql
    assert _run_sql("SELECT count(*) AS n FROM messages")["n"] == 1
    assert _run_sql("SELECT count(*) AS n FROM deliveries")["n"] == 1
    assert _run_sql("SELECT relay_via FROM messages LIMIT 1")["relay_via"] == "edgeone,cloudflare"


@pytest.mark.asyncio
async def test_bad_relay_message_id_422(app, setup):
    _, ep = setup
    r = await _post(app, ep, {"body": "x"}, headers={"X-Herald-Message-Id": "not-a-uuid"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_revoked_endpoint_401(app, setup):
    _, ep = setup
    from backend.tests.conftest import _run_sql
    _run_sql("UPDATE ingest_endpoints SET revoked_at = now() WHERE id = $1", ep["id"])
    r = await _post(app, ep, {"body": "x"})
    assert r.status_code == 401
```

- [ ] **Step 2:** 实现:
  - `services/ingest.py::create_ingest_message`:签名加 `message_id=None, received_at=None, relay_via=None`;INSERT 改:

```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

    stmt = pg_insert(tables.messages).values(**values).on_conflict_do_nothing(
        index_elements=[tables.messages.c.id]
    )
    result = await session.execute(stmt)
    duplicate = result.rowcount == 0
    if duplicate:
        await session.rollback()
        return serialize_uuid(values["id"]), True
```

  其中 `values["id"] = message_id or uuid.uuid4()`、`values["received_at"] = received_at or now`、`values["relay_via"] = relay_via`。非重复路径:规则评估、deliveries 插入、`last_used_at` 更新、commit 均照旧;返回 `(serialize_uuid(values["id"]), False)`(统一带连字符字符串,见 Interfaces)。
  - `routes/ingest.py`:认证成功后解析三个头(规则见 Interfaces);调用返回 `(mid, duplicate)` → `JSONResponse(status_code=200 if duplicate else 201, content={"message_id": mid, **({"duplicate": True} if duplicate else {})})`。
  - `services/ingest_endpoints.py::create_ingest_endpoint`:INSERT 增列 `key_sha256=sha256_hex(raw_token)`(import 自 `..auth.tokens`)。
- [ ] **Step 3:** `pytest backend/tests -v` 全绿;提交 `git commit -m "feat(ingest): idempotent message insert, relay headers, edge key digest"`

### Task 9: worker 可靠性修复

**Files:**
- Modify: `backend/worker.py`
- Test: `backend/tests/test_worker.py`(新建)

**Interfaces:**
- Produces:`_sweep_stale_sending(session, *, now) -> int`;`process_delivery_batch() -> int`(返回本轮认领数);worker 启动调用 `init_sentry()`。`process_delivery(session, delivery)` 签名不变。

- [ ] **Step 1:** 失败测试 `backend/tests/test_worker.py`(完整内容):

```python
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest

import backend.worker as worker_mod
from backend.tests.conftest import _run_sql


def _make_delivery(make_user, make_ingest_endpoint, make_channel, make_rule,
                   *, status="queued", updated_ago_minutes=0, attempts=0):
    user = make_user(email=f"{uuid.uuid4().hex[:8]}@x.com")
    ep = make_ingest_endpoint(user["id"])
    ch = make_channel(user["id"])
    rule = make_rule(user["id"], ch["id"])
    now = datetime.now(timezone.utc)
    mid, did = uuid.uuid4(), uuid.uuid4()
    _run_sql(
        "INSERT INTO messages (id, user_id, ingest_endpoint_id, received_at, body, priority, "
        "tags_json, extras_json, body_sha256, headers_json, query_json) "
        "VALUES ($1, $2, $3, $4, 'b', 3, '[]', '{}', 'x', '{}', '{}')",
        mid, user["id"], ep["id"], now,
    )
    _run_sql(
        "INSERT INTO deliveries (id, user_id, message_id, rule_id, channel_id, status, "
        "attempt_count, next_attempt_at, created_at, updated_at) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $8, $9)",
        did, user["id"], mid, rule["id"], ch["id"], status, attempts,
        now - timedelta(minutes=updated_ago_minutes), now - timedelta(minutes=updated_ago_minutes),
    )
    return did


def test_backoff_series():
    assert [worker_mod._backoff_seconds(n) for n in (1, 2, 3, 10)] == [5, 10, 20, 1800]


@pytest.mark.asyncio
async def test_stale_sending_requeued(make_user, make_ingest_endpoint, make_channel, make_rule):
    did = _make_delivery(make_user, make_ingest_endpoint, make_channel, make_rule,
                         status="sending", updated_ago_minutes=30)
    fresh = _make_delivery(make_user, make_ingest_endpoint, make_channel, make_rule,
                           status="sending", updated_ago_minutes=1)
    from backend.database import get_sessionmaker
    async with get_sessionmaker()() as session:
        swept = await worker_mod._sweep_stale_sending(session, now=datetime.now(timezone.utc))
    assert swept == 1
    assert _run_sql("SELECT status FROM deliveries WHERE id=$1", did)["status"] == "retry"
    assert _run_sql("SELECT status FROM deliveries WHERE id=$1", fresh)["status"] == "sending"


@pytest.mark.asyncio
async def test_batch_success_marks_sent(monkeypatch, make_user, make_ingest_endpoint,
                                        make_channel, make_rule):
    did = _make_delivery(make_user, make_ingest_endpoint, make_channel, make_rule)

    async def fake_dispatch(**kwargs):
        return True, {"http_status": 200}

    monkeypatch.setattr(worker_mod, "dispatch_channel_message", fake_dispatch)
    claimed = await worker_mod.process_delivery_batch()
    assert claimed == 1
    row = _run_sql("SELECT status, sent_at FROM deliveries WHERE id=$1", did)
    assert row["status"] == "sent" and row["sent_at"] is not None


@pytest.mark.asyncio
async def test_failure_retries_then_fails(monkeypatch, make_user, make_ingest_endpoint,
                                          make_channel, make_rule):
    did = _make_delivery(make_user, make_ingest_endpoint, make_channel, make_rule, attempts=9)

    async def fake_dispatch(**kwargs):
        return False, {"http_status": 500}

    monkeypatch.setattr(worker_mod, "dispatch_channel_message", fake_dispatch)
    await worker_mod.process_delivery_batch()
    row = _run_sql("SELECT status, attempt_count FROM deliveries WHERE id=$1", did)
    assert row["status"] == "failed" and row["attempt_count"] == 10


@pytest.mark.asyncio
async def test_disabled_rule_terminal(monkeypatch, make_user, make_ingest_endpoint,
                                      make_channel, make_rule):
    did = _make_delivery(make_user, make_ingest_endpoint, make_channel, make_rule)
    _run_sql("UPDATE rules SET enabled = FALSE")
    await worker_mod.process_delivery_batch()
    row = _run_sql("SELECT status, last_error FROM deliveries WHERE id=$1", did)
    assert row["status"] == "failed" and row["last_error"] == "rule_disabled"
```

- [ ] **Step 2:** 修改 `backend/worker.py`:
  - 新增(放在 `claim_due_deliveries` 之前):

```python
async def _sweep_stale_sending(session: AsyncSession, *, now: datetime) -> int:
    """Requeue deliveries stranded in 'sending' by a crashed worker."""
    tables = await get_tables()
    result = await session.execute(
        update(tables.deliveries)
        .where(
            tables.deliveries.c.status == "sending",
            tables.deliveries.c.updated_at < now - timedelta(minutes=10),
        )
        .values(status="retry", next_attempt_at=now, updated_at=now)
    )
    await session.commit()
    return result.rowcount or 0
```

  - `process_delivery_batch`(L265–282)整体替换:

```python
async def process_delivery_batch() -> int:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    sessionmaker = get_sessionmaker()

    async with sessionmaker() as session:
        swept = await _sweep_stale_sending(session, now=now)
        if swept:
            logger.warning("stale_sending_requeued", count=swept)
        deliveries = await claim_due_deliveries(
            session, now=now, batch_size=settings.worker_batch_size
        )

    # ponytail: serial, one session per delivery — provider HTTP is the bottleneck;
    # go concurrent-with-own-session per task if personal traffic ever outgrows this.
    for delivery in deliveries:
        async with sessionmaker() as session:
            await process_delivery(session, delivery)
    return len(deliveries)
```

  (import 对齐:`from .database import get_sessionmaker, get_tables`、`from sqlalchemy import update`、`from datetime import timedelta`。)
  - 主循环:`claimed = await process_delivery_batch()`;`if claimed < settings.worker_batch_size: await asyncio.sleep(settings.worker_poll_seconds)`(批满立即下一轮)。
  - `delivery_worker()` 开头 `setup_logging()` 之后加 `init_sentry()`(`from .observability import init_sentry`)。
- [ ] **Step 3:** `pytest backend/tests/test_worker.py -v` 通过;全套通过。提交:`git commit -m "fix(worker): per-delivery sessions, stale-sending sweep, sentry, drain-until-empty"`

### Task 10: 测试修剪与补齐

**Files:**
- Modify: `backend/tests/test_routes.py`(8 个 401 测试 → 1 个 parametrize;OpenAPI 断言保留并对齐新 schema)
- Modify: `backend/tests/test_providers.py`(gotify/ntfy priority 复制块 → parametrize)
- Modify: `backend/tests/test_core.py`(SSRF 测试 monkeypatch DNS;补规则 6 用例)

- [ ] **Step 1:** `test_routes.py`:L33–149 的 8 个函数合并:

```python
@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", [
    ("GET", "/api/messages"), ("GET", "/api/channels"), ("POST", "/api/channels"),
    ("GET", "/api/rules"), ("POST", "/api/rules"), ("GET", "/api/ingest-endpoints"),
    ("POST", "/api/ingest-endpoints"),
])
async def test_routes_require_auth(app, method, path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.request(method, path, json={} if method == "POST" else None)
    assert r.status_code == 401
```

同文件 OpenAPI 断言:删除 login/refresh 之外已不存在端点的引用(verify-email 等),其余保留。(`/api/edge-config` 不入本 parametrize——它的 404/401 语义在 Task 13 的 `test_edge_config.py` 单独覆盖。)
- [ ] **Step 2:** `test_providers.py`:`TestGotify` 的 4 个 priority 块(L229–273)与 `TestNtfy` 的 2 个(L157–186)分别 parametrize(`@pytest.mark.parametrize("msg_priority,expected", [...])`),断言不变。
- [ ] **Step 2b:** 同文件补 `TestMqtt`(审计确认的零覆盖 provider,`backend/providers/mqtt.py`):

```python
class TestMqtt:
    def test_encode_payload_variants(self):
        from backend.providers.mqtt import _encode_payload
        assert _encode_payload(b"raw") == b"raw"
        assert _encode_payload("str") == b"str"
        assert _encode_payload({"a": 1}) == b'{"a":1}'

    def test_send_mqtt_publish_success(self, monkeypatch):
        import backend.providers.mqtt as mqtt_mod
        calls = {}

        def fake_single(topic, **kwargs):
            calls["topic"] = topic
            calls["kwargs"] = kwargs

        monkeypatch.setenv("MQTT_BLOCK_PRIVATE_NETWORKS", "false")
        monkeypatch.setattr("paho.mqtt.publish.single", fake_single)
        ok, meta = mqtt_mod.send_mqtt_publish(
            broker_host="broker.example.com", broker_port=1883, topic="t/x",
            payload="hello", username=None, password=None, qos=0, retain=False,
            tls=False, tls_insecure=False, client_id=None, keepalive_seconds=60,
        )
        assert ok is True and calls["topic"] == "t/x"
        assert meta["broker_host"] == "broker.example.com"

    def test_send_mqtt_publish_rejects_private_host(self):
        from backend.providers.mqtt import send_mqtt_publish
        with pytest.raises(Exception):
            send_mqtt_publish(
                broker_host="192.168.1.10", broker_port=1883, topic="t",
                payload="x", username=None, password=None, qos=0, retain=False,
                tls=False, tls_insecure=False, client_id=None, keepalive_seconds=60,
            )
```

(`send_mqtt_publish` 是同步函数,若签名/异常类型与现文件不符,以 `backend/providers/mqtt.py` 现实现为准调整断言,不改生产代码。)
- [ ] **Step 3:** `test_core.py`:
  - `TestSSRF` 增 autouse fixture,monkeypatch `socket.getaddrinfo` 返回可控地址(公网名 → `93.184.216.34`,私网名照常),使断网可跑。
  - `TestRules` 补 6 用例(与设计文档 §3.11 对齐,断言语义照 `backend/core/rules.py` 现实现):`body.regex` 匹配/不匹配、无效 regex → False、`ingest_endpoint_ids` 过滤、`group` 精确匹配、组合过滤全 AND、`priority` 默认 3。
- [ ] **Step 4:** 全套绿;提交 `git commit -m "test(backend): parametrize repetition, offline ssrf tests, rule parity cases"`

---

## M2 Cloudflare 中继

### Task 11: 边缘共享模块(协议实现单一来源)

**Files:**
- Delete: `edge/src/`(整个目录:cloudflare-worker.mjs、lite.mjs、lite.test.mjs、providers.mjs、rules.mjs、template.mjs)
- Create: `edge/shared/http.mjs`、`edge/shared/auth.mjs`、`edge/shared/validate.mjs`、`edge/shared/relay.mjs`、`edge/shared/config-cache.mjs`
- Create: `edge/tests/shared.test.mjs`
- Modify: `edge/package.json`(scripts 指向新布局)

**Interfaces:**
- Produces(两平台入口消费):
  - `http.mjs`: `jsonResponse(body, status)`、`bearerToken(request) -> string`
  - `auth.mjs`: `sha256Hex(text) -> Promise<string>`、`constantTimeEqual(a, b)`、`authenticateIngest(config, endpointId, rawKey) -> Promise<endpoint|null>`
  - `validate.mjs`: `parseIngestEndpointIdFromPath(pathname) -> string`、`validatePayload(json) -> {ok, error?}`(两者从旧 `lite.mjs:17-88` 原样搬运)
  - `relay.mjs`: `buildEnvelope({endpointId, rawKey, body, via, nowIso, id, receivedAt}) -> envelope`、`parseRelayHeaders(request) -> {id, receivedAt, via}`、`forwardEnvelope(envelope, upstreamUrl, fetchImpl) -> Promise<{ok, permanent?, error?}>`、`backoffSeconds(attempts)`、`MAX_PENDING_AGE_MS = 7*24*3600*1000`
  - `config-cache.mjs`: `makeConfigLoader(getRaw, ttlMs=60000) -> (nowMs?) => Promise<config|null>`

- [ ] **Step 1:** `git rm -r edge/src`。建目录 `edge/shared`、`edge/tests`、`edge/cloudflare/src`、`edge/edgeone/edge-functions`。
- [ ] **Step 2:** 写共享模块。`validate.mjs` 从旧 `lite.mjs` L17–88 原样搬运两个函数(git 历史可查,或先 `git show HEAD~1:edge/src/lite.mjs`)。其余完整内容:

`edge/shared/http.mjs`:
```js
export function jsonResponse(body, status) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function bearerToken(request) {
  const h = request.headers.get("Authorization") || "";
  return h.startsWith("Bearer ") ? h.slice(7).trim() : "";
}
```

`edge/shared/auth.mjs`:
```js
export function constantTimeEqual(a, b) {
  const aa = String(a || "");
  const bb = String(b || "");
  if (aa.length !== bb.length) return false;
  let out = 0;
  for (let i = 0; i < aa.length; i++) out |= aa.charCodeAt(i) ^ bb.charCodeAt(i);
  return out === 0;
}

export async function sha256Hex(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function authenticateIngest(config, endpointId, rawKey) {
  const wanted = String(endpointId || "").replace(/-/g, "");
  const endpoint = (config?.ingest_endpoints || []).find(
    (ep) => String(ep.id).replace(/-/g, "") === wanted,
  );
  if (!endpoint || !rawKey) return null;
  const digest = await sha256Hex(String(rawKey).trim());
  return constantTimeEqual(digest, endpoint.key_sha256) ? endpoint : null;
}
```

`edge/shared/relay.mjs`:
```js
const PERMANENT_STATUSES = new Set([400, 401, 403, 404, 413, 415, 422]);
const UUID_RE = /^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$/i;

export const MAX_PENDING_AGE_MS = 7 * 24 * 3600 * 1000;

export function backoffSeconds(attempts) {
  return Math.min(3600, 5 * 2 ** Math.max(attempts - 1, 0));
}

export function parseRelayHeaders(request) {
  const rawId = (request.headers.get("X-Herald-Message-Id") || "").trim();
  const receivedAt = (request.headers.get("X-Herald-Received-At") || "").trim();
  const via = (request.headers.get("X-Herald-Relay-Via") || "")
    .toLowerCase().replace(/[^a-z,]/g, "").slice(0, 64);
  return {
    id: UUID_RE.test(rawId) ? rawId.toLowerCase() : null,
    receivedAt: Number.isFinite(Date.parse(receivedAt)) ? receivedAt : null,
    via: via || null,
  };
}

export function buildEnvelope({ endpointId, rawKey, body, via, nowIso, id, receivedAt }) {
  return {
    id: id || crypto.randomUUID(),
    endpoint_id: endpointId,
    received_at: receivedAt || nowIso,
    via,
    ingest_key: rawKey,
    body,
    attempts: 0,
    last_error: null,
  };
}

export async function forwardEnvelope(envelope, upstreamUrl, fetchImpl = fetch) {
  const url = `${String(upstreamUrl).replace(/\/+$/, "")}/api/ingest/${envelope.endpoint_id}`;
  try {
    const res = await fetchImpl(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Herald-Ingest-Key": envelope.ingest_key,
        "X-Herald-Message-Id": envelope.id,
        "X-Herald-Received-At": envelope.received_at,
        "X-Herald-Relay-Via": envelope.via,
      },
      body: envelope.body,
    });
    if (res.ok) return { ok: true };
    return { ok: false, permanent: PERMANENT_STATUSES.has(res.status), error: `upstream_status_${res.status}` };
  } catch (err) {
    return { ok: false, permanent: false, error: String(err).slice(0, 200) };
  }
}
```

`edge/shared/config-cache.mjs`:
```js
export function makeConfigLoader(getRaw, ttlMs = 60_000) {
  let cached = null;
  let cachedAt = 0;
  return async function load(nowMs = Date.now()) {
    if (cached && nowMs - cachedAt < ttlMs) return cached;
    const raw = await getRaw();
    if (raw) {
      cached = raw;
      cachedAt = nowMs;
    }
    return cached;
  };
}
```

- [ ] **Step 3:** `edge/tests/shared.test.mjs`:用 `node --test` 覆盖——`sha256Hex` 已知向量(`"abc"` → `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`);`authenticateIngest` 正确 key 命中/错误 key null/未知端点 null;`validatePayload` 沿旧 lite.test.mjs 的 422 用例(unknown field、missing body);`parseRelayHeaders` 合法/非法 UUID、via 字符清洗;`forwardEnvelope` 用假 fetch 断言 URL、四个头、ok/permanent/暂时三种结果;`backoffSeconds` 序列 5,10,20,…,3600 封顶;`makeConfigLoader` TTL 内不重取、过期重取。
- [ ] **Step 4:** `edge/package.json` scripts 改:`"test": "node --test tests/"`、`"lint": "find shared cloudflare edgeone tests -name '*.mjs' -o -name '*.js' | xargs -n1 node --check"`。跑 `npm --prefix edge test` 绿。提交:`git commit -m "feat(edge): shared relay protocol modules, drop lite dispatch mode"`

### Task 12: Cloudflare Worker + Durable Object

**Files:**
- Create: `edge/cloudflare/src/worker.mjs`
- Create: `edge/cloudflare/wrangler.toml`
- Delete: `edge/wrangler.toml`(旧)
- Test: `edge/tests/cloudflare.test.mjs`

**Interfaces:**
- Consumes: Task 11 全部共享模块。
- Produces: HTTP 面(设计文档 §2.4):`POST /api/ingest/{id}`→202、`GET /healthz`、`POST /admin/config`、`GET /admin/status`、`POST /relay/drain`(admin 三者 Bearer `RELAY_ADMIN_TOKEN`)。绑定:KV `EDGE_CONFIG`、DO `RELAY_BUFFER`(class `RelayBuffer`)、secret `RELAY_ADMIN_TOKEN`、var `UPSTREAM_URL`。

- [ ] **Step 1:** `edge/cloudflare/wrangler.toml`(完整内容;`kv id` 部署时填):

```toml
name = "herald-relay"
main = "src/worker.mjs"
compatibility_date = "2026-02-16"

[vars]
UPSTREAM_URL = "https://backend.example.com"

[[kv_namespaces]]
binding = "EDGE_CONFIG"
id = "REPLACE_WITH_NAMESPACE_ID"

[[durable_objects.bindings]]
name = "RELAY_BUFFER"
class_name = "RelayBuffer"

[[migrations]]
tag = "v1"
new_sqlite_classes = ["RelayBuffer"]
```

- [ ] **Step 2:** `edge/cloudflare/src/worker.mjs`(完整内容):

```js
import { jsonResponse, bearerToken } from "../../shared/http.mjs";
import { authenticateIngest } from "../../shared/auth.mjs";
import { parseIngestEndpointIdFromPath, validatePayload } from "../../shared/validate.mjs";
import { buildEnvelope, parseRelayHeaders, forwardEnvelope, backoffSeconds, MAX_PENDING_AGE_MS } from "../../shared/relay.mjs";
import { makeConfigLoader } from "../../shared/config-cache.mjs";

const MAX_BODY_BYTES = 1024 * 1024;
let configLoader = null;

function getConfigLoader(env) {
  if (!configLoader) {
    configLoader = makeConfigLoader(() => env.EDGE_CONFIG.get("config", "json"));
  }
  return configLoader;
}

function requireAdmin(request, env) {
  const token = bearerToken(request);
  return env.RELAY_ADMIN_TOKEN && token === env.RELAY_ADMIN_TOKEN;
}

async function handleIngest(request, env, url) {
  const endpointId = parseIngestEndpointIdFromPath(url.pathname);
  if (!endpointId) return jsonResponse({ code: "not_found", message: "not found" }, 404);
  if (request.method !== "POST") {
    return jsonResponse({ code: "method_not_allowed", message: "method not allowed" }, 405);
  }
  const contentType = (request.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase();
  if (contentType !== "application/json") {
    return jsonResponse({ code: "unsupported_media_type", message: "Content-Type must be application/json" }, 415);
  }

  const config = await getConfigLoader(env)();
  if (!config) return jsonResponse({ code: "misconfigured", message: "edge config not loaded" }, 500);

  const rawKey = request.headers.get("X-Herald-Ingest-Key") || "";
  const endpoint = await authenticateIngest(config, endpointId, rawKey);
  if (!endpoint) return jsonResponse({ code: "not_authenticated", message: "unauthorized" }, 401);

  const body = await request.text();
  if (new TextEncoder().encode(body).length > MAX_BODY_BYTES) {
    return jsonResponse({ code: "payload_too_large", message: "max 1MB" }, 413);
  }
  let parsed;
  try {
    parsed = JSON.parse(body);
  } catch {
    return jsonResponse({ code: "bad_request", message: "invalid JSON" }, 400);
  }
  const validation = validatePayload(parsed);
  if (!validation.ok) {
    return jsonResponse({ code: "validation_error", message: validation.error }, 422);
  }

  const relay = parseRelayHeaders(request);
  const via = relay.via ? `${relay.via},cloudflare` : "cloudflare";
  const envelope = buildEnvelope({
    endpointId: endpoint.id,
    rawKey: rawKey.trim(),
    body,
    via,
    nowIso: new Date().toISOString(),
    id: relay.id,
    receivedAt: relay.receivedAt,
  });

  const stub = env.RELAY_BUFFER.get(env.RELAY_BUFFER.idFromName("global"));
  const res = await stub.fetch("https://do/enqueue", {
    method: "POST",
    body: JSON.stringify(envelope),
  });
  if (!res.ok) return jsonResponse({ code: "buffer_error", message: "enqueue failed" }, 500);
  return jsonResponse({ message_id: envelope.id, status: "relayed" }, 202);
}

async function handleRequest(request, env) {
  const url = new URL(request.url);
  if (url.pathname === "/healthz") {
    return jsonResponse({ ok: true, mode: "relay", platform: "cloudflare" }, 200);
  }
  if (url.pathname === "/admin/config" && request.method === "POST") {
    if (!requireAdmin(request, env)) return jsonResponse({ code: "forbidden" }, 403);
    const body = await request.text();
    try {
      JSON.parse(body);
    } catch {
      return jsonResponse({ code: "bad_request", message: "invalid JSON" }, 400);
    }
    await env.EDGE_CONFIG.put("config", body);
    configLoader = null; // drop isolate cache so next read sees the new version
    return jsonResponse({ ok: true }, 200);
  }
  if (url.pathname === "/admin/status" || url.pathname === "/relay/drain") {
    if (!requireAdmin(request, env)) return jsonResponse({ code: "forbidden" }, 403);
    const stub = env.RELAY_BUFFER.get(env.RELAY_BUFFER.idFromName("global"));
    if (url.pathname === "/relay/drain") {
      if (request.method !== "POST") return jsonResponse({ code: "method_not_allowed" }, 405);
      return stub.fetch("https://do/drain", { method: "POST" });
    }
    const doStatus = await (await stub.fetch("https://do/status")).json();
    const config = await getConfigLoader(env)();
    return jsonResponse({ ...doStatus, config_version: config?.version ?? null }, 200);
  }
  return handleIngest(request, env, url);
}

export default {
  async fetch(request, env) {
    return handleRequest(request, env);
  },
};

export class RelayBuffer {
  constructor(ctx, env) {
    this.ctx = ctx;
    this.env = env;
    ctx.storage.sql.exec(
      "CREATE TABLE IF NOT EXISTS pending (" +
        "id TEXT PRIMARY KEY, endpoint_id TEXT NOT NULL, received_at TEXT NOT NULL, " +
        "via TEXT NOT NULL, ingest_key TEXT NOT NULL, body TEXT NOT NULL, " +
        "attempts INTEGER NOT NULL DEFAULT 0, next_attempt_ms INTEGER NOT NULL, " +
        "last_error TEXT, created_ms INTEGER NOT NULL)",
    );
    ctx.storage.sql.exec(
      "CREATE TABLE IF NOT EXISTS dead (" +
        "id TEXT PRIMARY KEY, envelope TEXT NOT NULL, reason TEXT, died_ms INTEGER NOT NULL)",
    );
  }

  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/enqueue" && request.method === "POST") {
      const e = await request.json();
      const now = Date.now();
      this.ctx.storage.sql.exec(
        "INSERT OR IGNORE INTO pending (id, endpoint_id, received_at, via, ingest_key, body, attempts, next_attempt_ms, last_error, created_ms) " +
          "VALUES (?, ?, ?, ?, ?, ?, 0, ?, NULL, ?)",
        e.id, e.endpoint_id, e.received_at, e.via, e.ingest_key, e.body, now, now,
      );
      // Forward ONLY the new envelope — never the backlog. During an outage the
      // backlog belongs to alarm(); draining it here would block every 202
      // behind serial upstream timeouts.
      const result = await this.forward(e.id);
      await this.rearmAlarm(now);
      return Response.json({ ok: true, forwarded: result.ok });
    }
    if (url.pathname === "/drain" && request.method === "POST") {
      return Response.json(await this.drainDue(true));
    }
    if (url.pathname === "/status") {
      const p = this.ctx.storage.sql
        .exec("SELECT COUNT(*) AS n, MIN(created_ms) AS oldest FROM pending").one();
      const d = this.ctx.storage.sql.exec("SELECT COUNT(*) AS n FROM dead").one();
      return Response.json({
        pending: p.n,
        dead: d.n,
        oldest_pending_at: p.oldest ? new Date(p.oldest).toISOString() : null,
      });
    }
    return Response.json({ error: "not_found" }, { status: 404 });
  }

  async alarm() {
    await this.drainDue();
  }

  // Forward one pending row by id. Returns {ok} and updates/deletes the row.
  async forward(id, nowMs = Date.now()) {
    const cursor = this.ctx.storage.sql.exec("SELECT * FROM pending WHERE id = ?", id);
    const rows = cursor.toArray();
    if (!rows.length) return { ok: true };
    const row = rows[0];
    if (nowMs - row.created_ms > MAX_PENDING_AGE_MS) {
      this._kill(row, "max_age_exceeded");
      return { ok: false };
    }
    const result = await forwardEnvelope(row, this.env.UPSTREAM_URL);
    if (result.ok) {
      this.ctx.storage.sql.exec("DELETE FROM pending WHERE id = ?", row.id);
    } else if (result.permanent) {
      this._kill(row, result.error);
    } else {
      const attempts = row.attempts + 1;
      this.ctx.storage.sql.exec(
        "UPDATE pending SET attempts = ?, next_attempt_ms = ?, last_error = ? WHERE id = ?",
        attempts, nowMs + backoffSeconds(attempts) * 1000, result.error, row.id,
      );
    }
    return { ok: result.ok };
  }

  // Batch cap 25: Workers free plan allows 50 subrequests per invocation —
  // do NOT raise this above ~40 or a full drain throws "Too many subrequests".
  async drainDue(force = false) {
    const now = Date.now();
    const rows = this.ctx.storage.sql
      .exec(
        force
          ? "SELECT id FROM pending ORDER BY created_ms LIMIT 25"
          : "SELECT id FROM pending WHERE next_attempt_ms <= ? ORDER BY created_ms LIMIT 25",
        ...(force ? [] : [now]),
      )
      .toArray();
    let drained = 0, failed = 0;
    for (const { id } of rows) {
      const result = await this.forward(id, now);
      if (result.ok) drained++;
      else failed++;
    }
    this.ctx.storage.sql.exec("DELETE FROM dead WHERE died_ms < ?", now - 30 * 24 * 3600 * 1000);
    await this.rearmAlarm(now);
    const dead = this.ctx.storage.sql.exec("SELECT COUNT(*) AS n FROM dead").one().n;
    return { drained, failed, dead };
  }

  async rearmAlarm(nowMs) {
    const next = this.ctx.storage.sql
      .exec("SELECT MIN(next_attempt_ms) AS ts FROM pending").one();
    if (next.ts != null) await this.ctx.storage.setAlarm(Math.max(next.ts, nowMs + 1000));
  }

  _kill(row, reason) {
    this.ctx.storage.sql.exec(
      "INSERT OR REPLACE INTO dead (id, envelope, reason, died_ms) VALUES (?, ?, ?, ?)",
      row.id,
      JSON.stringify({ ...row, ingest_key: "[redacted]" }),
      reason, Date.now(),
    );
    this.ctx.storage.sql.exec("DELETE FROM pending WHERE id = ?", row.id);
  }
}
```

- [ ] **Step 3:** `edge/tests/cloudflare.test.mjs`:`node --test` + 手写桩,不起 workerd。**测试策略(指令,不是选项)**:不要写内存 SQL 引擎去模拟 `storage.sql`(RelayBuffer 有约 10 种语句形状,模拟它本身就是过度工程);改为分层测——
  - 路由层:`handleRequest` 配 `env` 桩(`EDGE_CONFIG.get` 返回固定配置;`RELAY_BUFFER.get().fetch` 记录调用并返回 `Response.json({ok:true})`)。覆盖:healthz;admin 缺 token 与错 token 都 403(实现只发 403,没有 401 路径);`/admin/config` 非法 JSON 400;ingest 认证失败 401、未知字段 422、成功路径 → 断言 DO stub 收到的 envelope(via 追加 `cloudflare`、id 采用入站中继头)且响应 202。
  - 转发决策层:直接测共享 `forwardEnvelope`(fetch 桩:2xx → ok;500 → 暂时;422 → permanent)与 `backoffSeconds` —— 这已在 Task 11 覆盖,不重复。
  - `RelayBuffer` 的 SQL 编排(forward/drainDue/rearmAlarm)留给 Step 4 的 `wrangler dev` 手动冒烟(curl enqueue→status→drain),不写单测;在测试文件顶部注释注明该决定。
- [ ] **Step 4:** `npm --prefix edge test` 绿;`npx wrangler deploy --dry-run -c edge/cloudflare/wrangler.toml` 语法通过(不真部署);`npx wrangler dev -c edge/cloudflare/wrangler.toml` 本地冒烟 RelayBuffer:推一条配置(`/admin/config`)→ 发一条 ingest(上游填不可达地址)→ `/admin/status` 应见 `pending:1` → `/relay/drain`(强制重试)后 pending 仍为 1、attempts 递增。提交:`git commit -m "feat(edge): cloudflare relay worker with durable-object store-and-forward"`

### Task 13: 后端 edge-config 新形状 + 同步脚本

**Files:**
- Modify: `backend/edge_config.py`(重写导出形状)
- Modify: `backend/routes/__init__.py:68-74`(edge-config 路由改 Bearer 认证)
- Modify: `backend/schemas/edge.py`(新形状 models;删 `EdgeChannel`/`EdgeRule`)
- Create: `scripts/sync_edge_config.py`
- Test: `backend/tests/test_edge_config.py`(新建)

**Interfaces:**
- Produces:`GET /api/edge-config`,认证 `Authorization: Bearer <EDGE_SYNC_TOKEN>`(settings 里为空 → 一律 404;token 不匹配 → 401)。响应:`{"version": "<sha256[:16]>", "updated_at": "<iso>", "ingest_endpoints": [{"id": "<uuid>", "key_sha256": "<hex>"}]}`——**全体活跃用户**的未撤销未删除端点。`build_edge_config(session) -> dict`。

- [ ] **Step 1:** 失败测试 `backend/tests/test_edge_config.py`:未设 token → 404;错 token → 401;对 token → 200 且含 `key_sha256`、不含任何 `channels`/`rules`/`token_hash` 键;version 为 16 字符 hex。
- [ ] **Step 2:** 重写 `backend/edge_config.py::build_edge_config`:查询 `ingest_endpoints join users on is_active`(`revoked_at IS NULL AND deleted_at IS NULL`)→ `[{id, key_sha256}]`;`version` 沿现算法(canonical json sha256 前 16 位);删渠道/规则导出与 `_decrypt_channel_config`。路由:

```python
@router.get("/edge-config", response_model=EdgeConfigResponse)
async def get_edge_config(
    request: Request, session: AsyncSession = Depends(get_session)
) -> EdgeConfigResponse:
    settings = get_settings()
    if not settings.edge_sync_token:
        raise HTTPException(status_code=404, detail="not_found")
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token, settings.edge_sync_token):
        raise HTTPException(status_code=401, detail="not_authenticated")
    return EdgeConfigResponse(**(await build_edge_config(session)))
```

(`backend/routes/__init__.py` 需补 import:`import hmac`、`from fastapi import Request`、`from ..config import get_settings`——现文件只从 fastapi 引了 `APIRouter, Depends, HTTPException`。)

- [ ] **Step 3:** `scripts/sync_edge_config.py`(完整内容):

```python
#!/usr/bin/env python3
"""Sync edge relay config: pull from backend, push to each edge's /admin/config.

Usage:
  EDGE_SYNC_TOKEN=... RELAY_ADMIN_TOKEN=... \
  python3 scripts/sync_edge_config.py \
      --backend https://api.example.com \
      --edges https://relay.example.com,https://cn.example.com
"""

import argparse
import json
import os
import sys
import urllib.request


def _request(url: str, token: str, data: bytes | None = None) -> bytes:
    req = urllib.request.Request(
        url,
        data=data,
        method="POST" if data is not None else "GET",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", required=True)
    parser.add_argument("--edges", required=True, help="comma-separated edge base URLs")
    args = parser.parse_args()

    sync_token = os.environ.get("EDGE_SYNC_TOKEN", "")
    admin_token = os.environ.get("RELAY_ADMIN_TOKEN", "")
    if not sync_token or not admin_token:
        sys.exit("EDGE_SYNC_TOKEN and RELAY_ADMIN_TOKEN env vars are required")

    config = _request(f"{args.backend.rstrip('/')}/api/edge-config", sync_token)
    parsed = json.loads(config)
    for edge in [e.strip().rstrip("/") for e in args.edges.split(",") if e.strip()]:
        _request(f"{edge}/admin/config", admin_token, data=config)
        print(f"pushed version {parsed['version']} -> {edge}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4:** 全套后端测试绿。提交:`git commit -m "feat(edge-config): machine-credential export of endpoint digests, uniform sync script"`

---

## M3 EdgeOne 中继

### Task 14: EdgeOne Pages Edge Function

**Files:**
- Create: `edge/edgeone/edge-functions/[[default]].js`
- Create: `edge/edgeone/build.sh`(部署前复制 shared)
- Create: `edge/edgeone/project.json`(若 `edgeone pages` CLI 需要项目描述文件,按 CLI 实测决定;不需要则删)
- Modify: `edge/.gitignore`(加 `edgeone/edge-functions/_shared/`)
- Test: `edge/tests/edgeone.test.mjs`

**Interfaces:**
- Consumes: Task 11 共享模块(经 build.sh 复制为 `edge-functions/_shared/*.mjs`)。
- Produces: 与 CF 相同的 HTTP 面;差异:`platform: "edgeone"`,via 追加 `edgeone`,缓冲在 KV(`p_` 前缀,envelope 增记 `created_ms` = 入缓冲时刻,键序与 7 天超龄都以它为准),`/relay/drain` 每次至多处理 20 键并顺带清除 30 天前的 `d_` 键。
- **平台关键差异(EdgeOne Pages)**:KV 命名空间按绑定名注入为**全局变量** `EDGE_CONFIG`——**不在** `context.env` 上,`context.env.EDGE_CONFIG` 是 `undefined`;`context.env` 只承载普通环境变量 `RELAY_ADMIN_TOKEN`、`UPSTREAM_URL`(指向 CF Worker URL)。代码里统一经 `kvBinding()`(读 `globalThis.EDGE_CONFIG`)取 KV,测试注入 `globalThis.EDGE_CONFIG` 桩。

- [ ] **Step 1:** `edge/edgeone/build.sh`(完整内容;部署前必跑):

```bash
#!/usr/bin/env bash
# Copy shared protocol modules into the Pages function tree.
# EdgeOne Pages bundles only files under the project; keep _shared/ out of git.
set -euo pipefail
cd "$(dirname "$0")"
rm -rf edge-functions/_shared
mkdir -p edge-functions/_shared
cp ../shared/*.mjs edge-functions/_shared/
echo "shared modules copied"
```

- [ ] **Step 2:** `edge/edgeone/edge-functions/[[default]].js`(完整内容):

```js
import { jsonResponse, bearerToken } from "./_shared/http.mjs";
import { authenticateIngest } from "./_shared/auth.mjs";
import { parseIngestEndpointIdFromPath, validatePayload } from "./_shared/validate.mjs";
import {
  buildEnvelope, parseRelayHeaders, forwardEnvelope, backoffSeconds, MAX_PENDING_AGE_MS,
} from "./_shared/relay.mjs";
import { makeConfigLoader } from "./_shared/config-cache.mjs";

const MAX_BODY_BYTES = 1024 * 1024;
const DRAIN_BATCH = 20;
const DEAD_RETENTION_MS = 30 * 24 * 3600 * 1000;
let configLoader = null;

// EdgeOne Pages injects the bound KV namespace as a GLOBAL variable named after
// the binding — it is NOT on context.env (context.env.EDGE_CONFIG === undefined).
function kvBinding() {
  return globalThis.EDGE_CONFIG;
}

function getConfigLoader() {
  if (!configLoader) {
    configLoader = makeConfigLoader(async () => {
      const raw = await kvBinding().get("config", { type: "json" });
      return raw || null;
    });
  }
  return configLoader;
}

function pendingKey(envelope) {
  // key/aging clock = buffer-entry time (created_ms), NOT the sender-supplied
  // received_at — mirrors the CF DO semantics and closes a stale-timestamp abuse.
  const ts = String(envelope.created_ms).padStart(16, "0");
  return `p_${ts}_${envelope.id.replace(/-/g, "")}`;
}

function msFromKey(key) {
  return Number(key.slice(2, 18));
}

async function purgeExpiredDead(kv, nowMs) {
  const listed = await kv.list({ prefix: "d_", limit: 50 });
  for (const k of listed?.keys || []) {
    const key = k.key ?? k.name ?? k;
    if (nowMs - msFromKey(key) > DEAD_RETENTION_MS) await kv.delete(key);
  }
}

async function drainPending(env, limit, skipKey = null) {
  const kv = kvBinding();
  const listed = await kv.list({ prefix: "p_", limit });
  const keys = (listed?.keys || []).map((k) => k.key ?? k.name ?? k);
  let drained = 0, failed = 0, dead = 0;
  const now = Date.now();
  for (const key of keys) {
    if (key === skipKey) continue;
    const envelope = await kv.get(key, { type: "json" });
    if (!envelope) continue;
    const createdMs = envelope.created_ms || msFromKey(key);
    let outcome;
    if (now - createdMs > MAX_PENDING_AGE_MS) {
      outcome = { ok: false, permanent: true, error: "max_age_exceeded" };
    } else if (envelope.next_attempt_ms && envelope.next_attempt_ms > now) {
      continue;
    } else {
      outcome = await forwardEnvelope(envelope, env.UPSTREAM_URL);
    }
    if (outcome.ok) {
      await kv.delete(key);
      drained++;
    } else if (outcome.permanent) {
      await kv.put(
        `d_${key.slice(2)}`,
        JSON.stringify({ ...envelope, ingest_key: "[redacted]", last_error: outcome.error }),
      );
      await kv.delete(key);
      dead++;
    } else {
      const attempts = (envelope.attempts || 0) + 1;
      await kv.put(key, JSON.stringify({
        ...envelope,
        attempts,
        last_error: outcome.error,
        next_attempt_ms: now + backoffSeconds(attempts) * 1000,
      }));
      failed++;
    }
  }
  await purgeExpiredDead(kv, now);
  return { drained, failed, dead };
}

async function handleIngest(request, env, url, waitUntil) {
  const endpointId = parseIngestEndpointIdFromPath(url.pathname);
  if (!endpointId) return jsonResponse({ code: "not_found", message: "not found" }, 404);
  if (request.method !== "POST") {
    return jsonResponse({ code: "method_not_allowed", message: "method not allowed" }, 405);
  }
  const contentType = (request.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase();
  if (contentType !== "application/json") {
    return jsonResponse({ code: "unsupported_media_type", message: "Content-Type must be application/json" }, 415);
  }
  const config = await getConfigLoader()();
  if (!config) return jsonResponse({ code: "misconfigured", message: "edge config not loaded" }, 500);

  const rawKey = request.headers.get("X-Herald-Ingest-Key") || "";
  const endpoint = await authenticateIngest(config, endpointId, rawKey);
  if (!endpoint) return jsonResponse({ code: "not_authenticated", message: "unauthorized" }, 401);

  const body = await request.text();
  if (new TextEncoder().encode(body).length > MAX_BODY_BYTES) {
    return jsonResponse({ code: "payload_too_large", message: "max 1MB" }, 413);
  }
  let parsed;
  try {
    parsed = JSON.parse(body);
  } catch {
    return jsonResponse({ code: "bad_request", message: "invalid JSON" }, 400);
  }
  const validation = validatePayload(parsed);
  if (!validation.ok) {
    return jsonResponse({ code: "validation_error", message: validation.error }, 422);
  }

  const relay = parseRelayHeaders(request);
  const via = relay.via ? `${relay.via},edgeone` : "edgeone";
  const envelope = buildEnvelope({
    endpointId: endpoint.id,
    rawKey: rawKey.trim(),
    body,
    via,
    nowIso: new Date().toISOString(),
    id: relay.id,
    receivedAt: relay.receivedAt,
  });
  envelope.created_ms = Date.now();

  // Durability first: persist to KV before answering.
  const key = pendingKey(envelope);
  await kvBinding().put(key, JSON.stringify(envelope));

  waitUntil((async () => {
    const result = await forwardEnvelope(envelope, env.UPSTREAM_URL);
    if (result.ok) await kvBinding().delete(key);
    // opportunistic drain of stragglers; skip our own key (KV list is
    // eventually consistent and may still show the just-deleted entry)
    await drainPending(env, 3, key);
  })());

  return jsonResponse({ message_id: envelope.id, status: "relayed" }, 202);
}

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const waitUntil = (p) => context.waitUntil(p);

  if (url.pathname === "/healthz") {
    return jsonResponse({ ok: true, mode: "relay", platform: "edgeone" }, 200);
  }
  const isAdmin = url.pathname === "/admin/config" || url.pathname === "/admin/status"
    || url.pathname === "/relay/drain";
  if (isAdmin) {
    if (!env.RELAY_ADMIN_TOKEN || bearerToken(request) !== env.RELAY_ADMIN_TOKEN) {
      return jsonResponse({ code: "forbidden" }, 403);
    }
    if (url.pathname === "/admin/config" && request.method === "POST") {
      const body = await request.text();
      try {
        JSON.parse(body);
      } catch {
        return jsonResponse({ code: "bad_request", message: "invalid JSON" }, 400);
      }
      await kvBinding().put("config", body);
      configLoader = null;
      return jsonResponse({ ok: true }, 200);
    }
    if (url.pathname === "/relay/drain" && request.method === "POST") {
      return jsonResponse(await drainPending(env, DRAIN_BATCH), 200);
    }
    if (url.pathname === "/admin/status") {
      const pending = await kvBinding().list({ prefix: "p_", limit: 256 });
      const deadKeys = await kvBinding().list({ prefix: "d_", limit: 256 });
      const config = await getConfigLoader()();
      const pendingKeys = (pending?.keys || []).map((k) => k.key ?? k.name ?? k);
      return jsonResponse({
        pending: pendingKeys.length,
        dead: (deadKeys?.keys || []).length,
        config_version: config?.version ?? null,
        oldest_pending_at: pendingKeys.length
          ? new Date(msFromKey(pendingKeys[0])).toISOString()
          : null,
      }, 200);
    }
    return jsonResponse({ code: "method_not_allowed" }, 405);
  }
  return handleIngest(request, env, url, waitUntil);
}
```

> KV `list` 返回项的键字段名(`key` vs `name`)平台文档未定;代码已双兼容(`k.key ?? k.name`)。部署验证步骤(Step 4)确认实际形状。

- [ ] **Step 3:** `edge/tests/edgeone.test.mjs`:内存 KV 桩(Map 实现 get/put/delete/list-prefix)**注入到 `globalThis.EDGE_CONFIG`**(不是 env——与生产绑定方式一致;每个测试前重置,测试后 `delete globalThis.EDGE_CONFIG`),fetch 桩注入全局;`context` 桩提供 `{request, env: {RELAY_ADMIN_TOKEN, UPSTREAM_URL}, waitUntil}`(收集 promise,断言前 `await Promise.all`)。导入 `edge/edgeone/edge-functions/[[default]].js` **之前**先跑 `bash edge/edgeone/build.sh`(package.json 的 test script 前置:`"pretest": "bash edgeone/build.sh"`)。覆盖:202 且 KV 有 pending 键(键前缀毫秒 = created_ms);waitUntil 后转发成功 → 键被删;上游 5xx → 键保留且 attempts=1、next_attempt_ms 在未来;drain 空/成功/permanent → `d_` 键;30 天前的 `d_` 键被清除;admin 缺/错 token 均 403;config 写入后 60s 内命中缓存(注入 nowMs 验证 TTL);/admin/status 返回 `oldest_pending_at`。
- [ ] **Step 4(部署验证,人工)**:`cd edge/edgeone && bash build.sh && npx edgeone pages link && npx edgeone pages dev` 本地起服务(**link 是本地 KV 可用的前提**),curl 走一遍 healthz/admin/config/ingest;确认三件事:import `_shared` 打包成功、KV 绑定确实以全局变量注入(而非 env)、KV list 返回项的键字段名。把发现写进 `edge/README.md`;若与代码的双兼容假设不符,修正代码。
- [ ] **Step 5:** `npm --prefix edge test` 全绿;提交 `git commit -m "feat(edge): edgeone pages function with KV store-and-forward"`

### Task 15: 排空兜底 cron

**Files:**
- Create: `.github/workflows/edge-drain.yml`

- [ ] **Step 1:** 完整内容:

```yaml
name: edge-drain
on:
  schedule:
    - cron: "*/5 * * * *"
  workflow_dispatch:

permissions: {}

jobs:
  drain:
    runs-on: ubuntu-latest
    timeout-minutes: 2
    steps:
      - name: Drain EdgeOne relay buffer
        run: |
          curl -fsS -X POST \
            -H "Authorization: Bearer ${{ secrets.RELAY_ADMIN_TOKEN }}" \
            "${{ secrets.EDGEONE_DRAIN_URL }}"
```

(仓库 secrets 需配 `RELAY_ADMIN_TOKEN`、`EDGEONE_DRAIN_URL`,写入 Task 19 运维文档。)
- [ ] **Step 2:** 提交:`git commit -m "ci: scheduled edgeone drain fallback"`

---

## M4 运维、前端、文档

### Task 16: compose 生产化 + 开发分离

**Files:**
- Modify: `docker-compose.yml`(生产姿态)
- Create: `docker-compose.dev.yml`
- Modify: `backend/Dockerfile`(HEALTHCHECK)
- Modify: `start.sh`(改用 dev compose 与 migrate;`DJANGO_SECRET_KEY`→`SECRET_KEY`)

- [ ] **Step 1:** `docker-compose.yml` 整体替换:

```yaml
services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: herald
      POSTGRES_USER: herald
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U herald -d herald"]
      interval: 5s
      timeout: 3s
      retries: 5
    logging: &logging
      driver: json-file
      options: { max-size: "10m", max-file: "3" }

  migrate:
    build: ./backend
    command: ["python", "-m", "backend.migrate"]
    environment: &backend_env
      APP_ENV: production
      DATABASE_URL: postgresql://herald:${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}@db:5432/herald
      SECRET_KEY: ${SECRET_KEY:?set SECRET_KEY}
      JWT_SIGNING_KEY: ${JWT_SIGNING_KEY:-}
      CHANNEL_CONFIG_ENCRYPTION_KEY: ${CHANNEL_CONFIG_ENCRYPTION_KEY:?set CHANNEL_CONFIG_ENCRYPTION_KEY}
      EDGE_SYNC_TOKEN: ${EDGE_SYNC_TOKEN:-}
      CORS_ALLOWED_ORIGINS: ${CORS_ALLOWED_ORIGINS:-}
      FORWARDED_ALLOW_IPS: ${FORWARDED_ALLOW_IPS:-}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      LOG_FORMAT: json
      SENTRY_DSN: ${SENTRY_DSN:-}
    depends_on:
      db: { condition: service_healthy }
    restart: "no"

  api:
    build: ./backend
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment: *backend_env
    depends_on:
      db: { condition: service_healthy }
      migrate: { condition: service_completed_successfully }
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
    logging: *logging

  worker:
    build: ./backend
    command: ["python", "-m", "backend.worker"]
    restart: unless-stopped
    environment: *backend_env
    depends_on:
      db: { condition: service_healthy }
      migrate: { condition: service_completed_successfully }
    logging: *logging

volumes:
  pgdata:
```

(生产不发布 db 端口。`JWT_SIGNING_KEY: ${JWT_SIGNING_KEY:-}` 在宿主未设时注入**空串**——之所以安全,是因为 Task 2 的 config 用 `os.environ.get("JWT_SIGNING_KEY") or secret_key`,空串同样回落 `SECRET_KEY`;不要改回 `get(..., default)` 形式。前端容器按现状独立部署,不进 compose——与现状一致。)
- [ ] **Step 2:** `docker-compose.dev.yml`:db 服务加 `ports: ["${POSTGRES_PORT:-5432}:5432"]`、密码固定 `herald`、db 名 `herald_dev`;api/worker 用 `APP_ENV: development` 与 dev 默认密钥。内容照上文精简(允许 `SECRET_KEY:-dev-insecure`)。
- [ ] **Step 3:** `backend/Dockerfile` 在 `EXPOSE 8000` 后加:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD curl -fsS http://localhost:8000/health || exit 1
```

- [ ] **Step 4:** `start.sh`:`docker compose up -d db` → `docker compose -f docker-compose.dev.yml up -d db`;bootstrap 行 → `uv run --project backend --locked python -m backend.migrate`;`DJANGO_SECRET_KEY` 出现处 → `SECRET_KEY`;db 名 `herald_dev` 保持。跑 `./start.sh headless` 验证起得来、`curl localhost:38000/health` 返回 200。
- [ ] **Step 5:** 验证生产 compose 拒绝缺密钥:`docker compose config` 无 env 时报 `set SECRET_KEY` 错。提交:`git commit -m "ops: production-posture compose with dev override, container healthchecks"`

### Task 17: 多架构镜像 + 备份脚本

**Files:**
- Modify: `.github/workflows/docker-images.yml:36`
- Create: `scripts/backup_db.sh`

- [ ] **Step 1:** `BUILD_PLATFORM: linux/arm64` → `BUILD_PLATFORM: linux/amd64,linux/arm64`。
- [ ] **Step 2:** `scripts/backup_db.sh`(完整内容):

```bash
#!/usr/bin/env bash
# Nightly Postgres backup. Cron example:
#   0 3 * * * BACKUP_DIR=/var/backups/herald /path/to/scripts/backup_db.sh
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
COMPOSE_DB_SERVICE="${COMPOSE_DB_SERVICE:-db}"

# cron runs with cwd=$HOME; docker compose needs the repo root to find the compose file
cd "$(dirname "$0")/.."

mkdir -p "$BACKUP_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
docker compose exec -T "$COMPOSE_DB_SERVICE" pg_dump -U herald herald \
  | gzip > "$BACKUP_DIR/herald-$stamp.sql.gz"
find "$BACKUP_DIR" -name 'herald-*.sql.gz' -mtime "+$KEEP_DAYS" -delete
echo "backup written: $BACKUP_DIR/herald-$stamp.sql.gz"
```

`chmod +x scripts/backup_db.sh`。
- [ ] **Step 3:** 提交:`git commit -m "ops: multi-arch images, database backup script"`

### Task 18: 前端清理(渠道表单状态 + 死组件)

**Files:**
- Modify: `frontend/src/pages/dashboard/channels/formState.ts`(195 行 → 每渠道一个 state 对象)
- Modify: `frontend/src/pages/dashboard/channels/CreateChannelCard.tsx` 与四个 `*ChannelForm.tsx`(props 对齐)
- Delete: `frontend/src/components/ui/tooltip.tsx`
- Modify: `frontend/src/main.tsx:4,11-13`(删 TooltipProvider)
- Delete(承接 Task 4 的后端删除,前端同步):`frontend/src/components/ResetPasswordForm.tsx`、`frontend/src/components/VerifyEmailClient.tsx`、`frontend/src/pages/auth/ForgotPasswordPage.tsx`
- Modify(同上):`frontend/src/router.tsx`(删 `/forgot-password`、`/reset-password`、`/verify-email` 三路由与 :2-3,:8 的 import)、`frontend/src/components/LoginForm.tsx:87-94`(删忘记密码链接)、`frontend/src/pages/dashboard/AccountPage.tsx`(删验证状态区 :56-63、resend 按钮 :64-74、`callNoBody` :23-33)、`frontend/src/pages/auth/SignupPage.tsx:31,63`(删验证文案)、`frontend/src/lib/types.ts:10`(删 `email_verified_at`)、`DashboardPage.tsx:22,74-76`(删未验证横幅)、`ChannelsPage.tsx:13`、`RulesPage.tsx:15`、`IngestEndpointsPage.tsx:24`、`MessagesPage.tsx:26`、`MessageDetailPage.tsx:26`(删 `canCreate/canMutate/canDelete` 验证门禁,操作恒可用)

- [ ] **Step 0:** 先做上面"承接 Task 4"的删改;`grep -rn "email_verified\|verify-email\|forgot-password\|reset-password\|resend-verification" frontend/src/` 零命中。
- [ ] **Step 1:** `formState.ts` 重构:29 个 `useState` 收敛为 `const [bark, setBark] = useState<BarkFormValues>(EMPTY_BARK)` 等四个对象 + 一个 `common`(name/type);`resetForm` = 四个 `setX(EMPTY_X)`;导出类型与初值常量。四个表单组件的 props 从散装 setter 改为 `(values, onChange)` 对。行为验证:`pnpm --dir frontend build` + 手动 `./start.sh full` 建一个 bark 渠道成功。
- [ ] **Step 2:** 删 tooltip 文件与 provider 包装。lint+build 绿。
- [ ] **Step 3:** 提交:`git commit -m "refactor(frontend): collapse channel form state, drop dead tooltip"`

### Task 19: 文档全面对齐

**Files:**
- Modify: `README.md`、`docs/01_prd.md`、`docs/02_architecture.md`、`docs/03_data_model.md`、`docs/04_api_spec.md`、`docs/06_security_privacy.md`、`docs/07_operations.md`、`docs/09_repo_structure.md`、`docs/10_edge.md`、`docs/openapi.yaml`、`docs/AGENTS.md`、`AGENTS.md`、`backend/AGENTS.md`、`edge/AGENTS.md`、`edge/README.md`
- Delete: `docs/11_edge_lite_feasibility.md`

- [ ] **Step 1:** **删守卫**:`docs/AGENTS.md:68`("Do not reintroduce EdgeOne/proxy-mode language...")与 `docs/02_architecture.md:95`("Cloudflare-only runtime...")两行删除。
- [ ] **Step 2:** `docs/10_edge.md` 重写为中继协议文档(内容 = 设计文档 §2.3–2.5:拓扑、请求/响应、envelope、admin 端点、两平台差异、部署步骤含 wrangler 与 edgeone CLI 命令、ICP 前提、GH secrets 清单)。
- [ ] **Step 3:** `docs/07_operations.md` 重写:env 清单(新名与新增项)、生产 compose 步骤(`POSTGRES_PASSWORD/SECRET_KEY/CHANNEL_CONFIG_ENCRYPTION_KEY/EDGE_SYNC_TOKEN` 必填)、`python -m backend.migrate`、`herald-backend reset-password`、备份 cron 行、`scripts/sync_edge_config.py` 用法、限流参数、`FORWARDED_ALLOW_IPS` 反代说明。
- [ ] **Step 4:** `docs/03_data_model.md` 对齐新表名/新列;`docs/04_api_spec.md` 与 `docs/openapi.yaml`:删 verify/forgot/reset/resend 四端点,ingest 加 200 duplicate 响应与三个中继头,edge-config 改 Bearer 说明;`docs/06_security_privacy.md` 更新密钥表(设计文档 §2.5 照抄)。
- [ ] **Step 5:** README 重写 Quick Start(migrate 替代 bootstrap;边缘部署一节);`docs/09_repo_structure.md` 与三个包 AGENTS.md 对齐新布局(`edge/{shared,cloudflare,edgeone,tests}`)。`git rm docs/11_edge_lite_feasibility.md`。
- [ ] **Step 6:** 验证:`grep -rn "bootstrap_dev_db\|DJANGO_SECRET_KEY\|beacon_\|accounts_\|email_verified\|lite mode\|edge-lite" README.md docs/ *.md backend/AGENTS.md edge/ frontend/AGENTS.md --include="*.md"` 零命中。提交:`git commit -m "docs: align all docs with relay architecture and clean schema"`

### Task 20: 终验(整体 DoD)

- [ ] **Step 1:** 全量检查:

```bash
uv run --project backend --locked pytest backend/tests -v          # 全绿
npm --prefix edge test && npm --prefix edge run lint               # 全绿
pnpm --dir frontend lint && pnpm --dir frontend build              # 通过
python3 scripts/sync_version.py --check                            # 对齐
git grep -nE "beacon_|accounts_|DJANGO_SECRET_KEY|bootstrap_dev_db" -- ':!docs/12*' ':!docs/13*'   # 零命中
git grep -nE "email_verified" -- ':!docs/12*' ':!docs/13*'          # 零命中(测试里的死端点 URL 字面量不含此串)
git diff main --unified=0 -- ':!docs/12*' ':!docs/13*' | grep -nE '^\+.*(TODO|FIXME)'   # 零命中(DoD 7)
```

- [ ] **Step 2:** 行数验证:`git diff --stat main` 后端(backend/,不含 tests)应净减 ≥ 800 行。
- [ ] **Step 3:** 按设计文档 §4 的 DoD 条目 1–3 做部署演练(全新部署、断链 30 分钟、kill -9 worker),逐条记录结果到 PR 描述。无法在本机完成的(EdgeOne 真实部署)标注为发布前人工步骤。
- [ ] **Step 4:** 提交并合并:`git commit`(如有收尾)→ 推分支开 PR,PR 描述含 DoD 勾选清单。

---

## Self-Review 检查单(计划作者已执行,执行者复核)

1. **设计覆盖**:设计文档 §3.1–3.11 每小节均有对应 Task(3.1→T1,3.2→T4,3.3→T9,3.4→T8,3.5→T2/5/6/7,3.6→T12,3.7→T14/15,3.8→T13,3.9→T16/17/19,3.10→T18,3.11→T3/9/10/11–14)。审计 25 项确认发现全部映射(死信装置 T4+T18、edge 认证 T8/11、worker T9、CORS T6、验证框架 T7、垫片 T5、迁移 T1、备份/镜像 T17、compose T16、限流 T6、Sentry T2/T9、文档守卫 T19、测试缺口 T3/8/9/10 含 MQTT provider T10 Step 2b)。
2. **类型一致**:`sha256_hex`(T2 定义,T8/T3 消费);`apply_migrations`(T1 定义,T3 消费);工厂与 `_run_sql`(T3 定义,T8/9 消费);`normalize_channel_config`(T7 定义,channel_operations 消费);envelope 字段(T11 定义,T12/14 消费;EdgeOne 侧额外追加 `created_ms`);`key_sha256` 列(T1 定义,T8 写入,T13 导出,T11 校验);message_id 统一为带连字符 UUID 字符串(T8)。
3. **顺序依赖**:T3 依赖 T1/T2;T8 依赖 T3/T6(429 用例需限流中间件);T9 依赖 T3;T12/14 依赖 T11;T13 依赖 T8(key_sha256 已入库);T16 依赖 T1(migrate 存在);T18 承接 T4 的前端面(T4 后、T18 前前端的 verify/reset 页面短暂指向已删端点,构建不受影响)。按编号顺序执行即满足。
4. **本计划经过 6 维对抗评审(48 项发现)并已回修**,包括:EdgeOne KV 以全局变量注入(非 `context.env`)、DO `/enqueue` 只转发本条不排积压、conftest `_run_sql` 事件循环安全、Starlette `MutableHeaders` 替换自制类、渠道错误形状去 DRF 化等。执行中若发现文档与仓库现实不符,以"设计文档的意图 + 仓库现实"为准修正,并在 PR 描述记录偏差。
