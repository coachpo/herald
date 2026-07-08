# Herald 加固更新 实施计划(第二轮)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复第一轮升级复检确认的 7 项 major(F1–F7)与 12 项 minor(M1–M12),达到可上线标准。问题清单、决策与理由见 `docs/15_hardening_design.md` §1(与本计划同时提交,执行前通读;本计划关键处已内联必要内容,可独立执行)。

**Architecture:** 无新架构,全部为点状修复:限流键规范化、EdgeOne 排空分页化、后端 priority 归一、CF 入口延迟解耦、脚本/文档补强、测试补齐。

**Tech Stack:** 与现状一致。**不新增任何依赖。**

## Global Constraints

- 不新增依赖;无新抽象层;无兼容垫片(零兼容授权仍有效)。中间件保持纯 ASGI。
- 每个 Task 一次提交,Conventional Commits,英文 message。
- 测试命令:后端 `uv run --project backend --locked pytest backend/tests -v`(需本地 Postgres:`docker run -d --name herald-test-pg -e POSTGRES_DB=herald -e POSTGRES_USER=herald -e POSTGRES_PASSWORD=herald -p 5432:5432 postgres:16-alpine`);边缘 `npm --prefix edge test && npm --prefix edge run lint`;前端 `pnpm --dir frontend lint && pnpm --dir frontend build`。
- 本计划代码块按 commit **`08eb0df`** 的源码写成;若执行时基线漂移,以"设计意图 + 仓库现实"修正,并在 PR 描述记录偏差。

---

## 交接上下文

- 第一轮升级已落地(`b51ce77..5f6e1fc`),文档收编已提交(`08eb0df`,一次性的升级计划/验证文档已删除,内容并入 `docs/07`/`docs/10` 等)。三套测试全绿(后端 118 / 边缘 21 / 前端构建)。**不要引用已删除的 docs/12–14。**
- 关键现状锚点(已核对):
  - 限流:`backend/middleware.py` `RateLimitMiddleware`(`_match`/`_allow`;`uuid`、`time`、`Response` 已 import)。
  - ingest 校验:`backend/services/ingest.py` priority 分支(`priority_val = data.get("priority", 3)` 附近)。
  - worker:`backend/worker.py`——消息查询**只按 id、不过滤 `deleted_at`**(L150-161);`message_not_found` 分支在 L163-174;`dispatch_channel_message` 为模块级导入(monkeypatch 目标 `backend.worker.dispatch_channel_message`)。
  - crypto:`backend/core/crypto.py` 的 `_fernet_from_settings` 带 `@lru_cache(maxsize=1)`——改密钥的测试**必须**同时 `cache_clear()` 它。
  - CF Worker:`edge/cloudflare/src/worker.mjs`(`requireAdmin` L23-26;DO `/enqueue` L138-155;`drainDue` L204;`rearmAlarm` L227)。
  - EdgeOne:`edge/edgeone/edge-functions/[[default]].js`(`drainPending(env, limit, skipKey)` L72-104;`saveOutcome` L49-70;admin 块 L171-206;`pendingKey` 键形 `p_<16位ms>_<32位id>`,id 起始下标 19)。
  - EdgeOne 测试:`edge/tests/edgeone.test.mjs` 已有助手 **`MemoryKV`(Map 封装)、`context()`、`writeConfig()`**,并已有 stub `Date.now` 的先例(约 L77-79);KV 桩经 `globalThis.EDGE_CONFIG` 注入;`pretest` 自动跑 `edgeone/build.sh` 重拷 `_shared`。
  - 共享:`edge/shared/auth.mjs`(`sha256Hex`/`constantTimeEqual` 已存在)、`edge/shared/config-cache.mjs`、`edge/shared/relay.mjs`(`MAX_PENDING_AGE_MS = 7 天`)。
  - 脚本:`scripts/sync_edge_config.py`(推送循环 L37-40)、`scripts/backup_db.sh`、`backend/migrate.py`。
  - schema 事实(Task 4 用):`GET /api/messages` 返回 `{"messages": [MessageSummary]}`,条目字段是 **`body_preview`**(无 `body`);端点创建响应 `{endpoint, ingest_key, ingest_url}`;撤销 `POST /api/ingest-endpoints/{id}/revoke`。
  - `.gitignore` 含 `.env.*` —— 会忽略 `.env.example`,Task 10 需加豁免行。

---

### Task 0: 基线

- [ ] **Step 1:** 通读 `docs/15_hardening_design.md`。
- [ ] **Step 2:** 建分支并提交两份规划文档(防丢):

```bash
git checkout -b hardening
git add docs/15_hardening_design.md docs/16_hardening_plan.md
git commit -m "docs: add hardening design and implementation plan"
```

- [ ] **Step 3:** 起测试库(Global Constraints 中的 docker 命令,已在跑则跳过);三套测试基线全绿并记录实际数字。

### Task 1: 限流修复(F1)

**Files:**
- Modify: `backend/middleware.py`(`_match`、`_allow`)
- Test: `backend/tests/test_middleware.py`(+2 用例)

**Interfaces:**
- Produces:ingest 桶键 = `ingest:{客户端IP}:{UUID规范hex}`(段解析失败按原文);auth 桶键不变;`_buckets` 超 1 万条时剔除闲置 >120s 条目。

- [ ] **Step 1:** 失败测试(追加到 `test_middleware.py`,该文件已 import `AsyncClient/ASGITransport/pytest`):

```python
import uuid as _uuid


def _fresh_app(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    from backend.config import get_settings
    get_settings.cache_clear()
    from backend.app import create_app
    return create_app()


@pytest.mark.asyncio
async def test_ingest_rate_limit_bucket_is_canonical(monkeypatch):
    app = _fresh_app(monkeypatch, RATE_LIMIT_INGEST_PER_MINUTE="2")
    eid = _uuid.uuid4()
    forms = [str(eid), eid.hex, str(eid).upper()]  # 同一端点的三种写法
    statuses = []
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        for form in forms:
            r = await c.post(
                f"/api/ingest/{form}", json={"body": "x"},
                headers={"X-Herald-Ingest-Key": "bogus"},
            )
            statuses.append(r.status_code)
    # 限流在认证前消耗:前两发吃掉同一桶的 2 个令牌(认证 401),
    # 第三种写法必须命中同一规范化桶 → 429
    assert statuses == [401, 401, 429]


@pytest.mark.asyncio
async def test_ingest_rate_limit_differs_per_endpoint(monkeypatch):
    app = _fresh_app(monkeypatch, RATE_LIMIT_INGEST_PER_MINUTE="1")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.post(f"/api/ingest/{_uuid.uuid4()}", json={"body": "x"},
                          headers={"X-Herald-Ingest-Key": "bogus"})
        r2 = await c.post(f"/api/ingest/{_uuid.uuid4()}", json={"body": "x"},
                          headers={"X-Herald-Ingest-Key": "bogus"})
    assert (r1.status_code, r2.status_code) == (401, 401)  # 不同端点不同桶
```

- [ ] **Step 2:** 实现——`_match` 整体替换:

```python
    def _match(self, scope: Scope) -> tuple[str, int] | None:
        if scope.get("method") != "POST":
            return None
        path = scope.get("path", "")
        settings = get_settings()
        client = scope.get("client") or ("", 0)
        if path.startswith("/api/ingest/"):
            segment = path.rsplit("/", 1)[-1]
            # 认证器接受同一 UUID 的多种写法(带杠/无杠/大小写),桶键必须先规范化,
            # 否则限流可被写法乘法绕过;IP 维度防止第三方垃圾流量饿死租户的桶。
            try:
                canonical = uuid.UUID(segment).hex
            except ValueError:
                try:
                    canonical = uuid.UUID(hex=segment).hex
                except ValueError:
                    canonical = segment
            return (
                f"ingest:{client[0]}:{canonical}",
                settings.rate_limit_ingest_per_minute,
            )
        if path in self._AUTH_PATHS:
            return (f"auth:{client[0]}", settings.rate_limit_auth_per_minute)
        return None
```

`_allow` 的全清分支替换:

```python
        if len(self._buckets) > 10_000:
            cutoff = now - 120.0
            for stale_key in [k for k, (_, ts) in self._buckets.items() if ts < cutoff]:
                del self._buckets[stale_key]
```

- [ ] **Step 3:** `pytest backend/tests/test_middleware.py -v` 与全套通过。提交:`git commit -m "fix(ratelimit): canonical per-ip ingest buckets, stale eviction instead of global clear"`

### Task 2: priority 平价归一(F3)

**Files:**
- Modify: `backend/services/ingest.py`(priority 分支)
- Test: `backend/tests/test_ingest_api.py`(+1 用例)

- [ ] **Step 1:** 失败测试(追加;`_post`/`setup` 为该文件现有助手):

```python
@pytest.mark.asyncio
async def test_integral_float_priority_accepted(app, setup):
    # JS 中继端把 3.0 判为整数放行;后端必须同样宽容,否则 202 后静默死信
    _, ep = setup
    assert (await _post(app, ep, {"body": "x", "priority": 3.0})).status_code == 201
    assert (await _post(app, ep, {"body": "x", "priority": 3.5})).status_code == 422
```

- [ ] **Step 2:** `services/ingest.py` 在 `priority_val = data.get("priority", 3)` 之后插入:

```python
    if isinstance(priority_val, float) and priority_val.is_integer():
        priority_val = int(priority_val)  # JSON 只有一种数字类型;JS 端 3.0 与 3 不可区分
```

- [ ] **Step 3:** 全套绿;提交 `git commit -m "fix(ingest): accept integral-float priority to match edge validation"`

### Task 3: worker 状态机测试补齐(F6)

**Files:**
- Test: `backend/tests/test_worker.py`(+3 用例;复用现有 `_make_delivery` 助手与 import——`worker_mod`、`_run_sql`、`datetime/timezone` 均已在文件中)

- [ ] **Step 1:** 追加三个用例(完整内容):

```python
@pytest.mark.asyncio
async def test_failure_below_max_schedules_retry(monkeypatch, make_user, make_ingest_endpoint,
                                                 make_channel, make_rule):
    did = _make_delivery(make_user, make_ingest_endpoint, make_channel, make_rule)

    async def fake_dispatch(**kwargs):
        return False, {"http_status": 500}

    monkeypatch.setattr(worker_mod, "dispatch_channel_message", fake_dispatch)
    assert await worker_mod.process_delivery_batch() == 1
    row = _run_sql("SELECT status, attempt_count, next_attempt_at FROM deliveries WHERE id=$1", did)
    assert row["status"] == "retry"
    assert row["attempt_count"] == 1
    delta = (row["next_attempt_at"] - datetime.now(timezone.utc)).total_seconds()
    assert 0 < delta <= 6  # 首次退避 = 5s
    # 退避未到期:立刻再跑一轮必须认领不到
    assert await worker_mod.process_delivery_batch() == 0


@pytest.mark.asyncio
async def test_disabled_channel_terminal(monkeypatch, make_user, make_ingest_endpoint,
                                         make_channel, make_rule):
    did = _make_delivery(make_user, make_ingest_endpoint, make_channel, make_rule)
    _run_sql("UPDATE channels SET disabled_at = now()")

    async def must_not_dispatch(**kwargs):
        raise AssertionError("terminal path must not dispatch")

    monkeypatch.setattr(worker_mod, "dispatch_channel_message", must_not_dispatch)
    assert await worker_mod.process_delivery_batch() == 1
    row = _run_sql("SELECT status, last_error FROM deliveries WHERE id=$1", did)
    assert row["status"] == "failed" and row["last_error"] == "channel_disabled"


@pytest.mark.asyncio
async def test_missing_message_terminal(monkeypatch, make_user, make_ingest_endpoint,
                                        make_channel, make_rule):
    # 该分支经数据无法构造:FK 级联删除会连带删掉 delivery,而 worker 的消息
    # 查询不过滤 deleted_at(backend/worker.py:150-161)。这是防御性分支,
    # 直接以伪造的认领行调用 process_delivery 是唯一确定性路径。
    import uuid
    from types import SimpleNamespace

    did = _make_delivery(make_user, make_ingest_endpoint, make_channel, make_rule)
    real = _run_sql(
        "SELECT user_id, rule_id, channel_id, attempt_count FROM deliveries WHERE id=$1", did)

    async def must_not_dispatch(**kwargs):
        raise AssertionError("terminal path must not dispatch")

    monkeypatch.setattr(worker_mod, "dispatch_channel_message", must_not_dispatch)
    from backend.database import get_sessionmaker
    claimed = SimpleNamespace(
        id=did, user_id=real["user_id"], message_id=uuid.uuid4(),  # 不存在的消息
        rule_id=real["rule_id"], channel_id=real["channel_id"],
        status="sending", attempt_count=real["attempt_count"],
        next_attempt_at=None, last_error=None,
    )
    async with get_sessionmaker()() as session:
        await worker_mod.process_delivery(session, claimed)
    row = _run_sql("SELECT status, last_error FROM deliveries WHERE id=$1", did)
    assert row["status"] == "failed" and row["last_error"] == "message_not_found"
```

(`SimpleNamespace` 字段集以 `claim_due_deliveries` 实际 SELECT 的列为准——`process_delivery` 只按属性访问;若它访问了上面未列的属性,补上即可。)
- [ ] **Step 2:** 三个用例绿、全套绿。提交 `git commit -m "test(worker): retry scheduling and remaining terminal paths"`

### Task 4: 认证后 CRUD 行为测试(F7)

**Files:**
- Test: `backend/tests/test_dashboard_api.py`(新建)

**Interfaces:**
- Consumes:conftest 的 `app`、`_run_sql`;auth API。字段名依据已核对的 schema:消息列表为 `{"messages": [...]}` 且条目字段是 `body_preview`;端点创建响应 `{endpoint, ingest_key, ingest_url}`。渠道/规则响应若为包裹形状,按 `backend/schemas/channels.py`/`rules.py` 现有模型取值(原则:改测试不改产品)。

- [ ] **Step 1:** 新建文件(完整内容):

```python
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from backend.tests.conftest import _run_sql

PUBLIC_IP_URL = "https://93.184.216.34"  # IP 字面量:SSRF 校验不查 DNS,离线可跑


async def _authed_client(app):
    c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    email = f"{uuid.uuid4().hex[:8]}@x.com"
    await c.post("/api/auth/signup", json={"email": email, "password": "pw-123456"})
    login = (await c.post("/api/auth/login", json={"email": email, "password": "pw-123456"})).json()
    c.headers["Authorization"] = f"Bearer {login['access_token']}"
    return c


async def _create_channel(c, name):
    r = await c.post("/api/channels", json={
        "type": "ntfy", "name": name,
        "config": {"server_base_url": PUBLIC_IP_URL, "topic": "t"},
    })
    assert r.status_code in (200, 201), r.text
    body = r.json()
    return body["channel"]["id"] if "channel" in body else body["id"]


@pytest.mark.asyncio
async def test_channel_create_and_list_roundtrip(app):
    async with await _authed_client(app) as c:
        await _create_channel(c, "ch1")
        listed = (await c.get("/api/channels")).json()
        items = listed["channels"] if isinstance(listed, dict) else listed
        assert any(ch["name"] == "ch1" for ch in items)


@pytest.mark.asyncio
async def test_rule_create(app):
    async with await _authed_client(app) as c:
        channel_id = await _create_channel(c, "ch2")
        r = await c.post("/api/rules", json={
            "name": "r1", "enabled": True, "channel_id": channel_id,
            "filter": {}, "payload_template": {},
        })
        assert r.status_code in (200, 201), r.text


@pytest.mark.asyncio
async def test_ingest_endpoint_create_then_revoke_blocks_ingest(app):
    async with await _authed_client(app) as c:
        created = (await c.post("/api/ingest-endpoints", json={"name": "ep1"})).json()
        key = created["ingest_key"]
        endpoint_id = created["endpoint"]["id"]
        ok = await c.post(f"/api/ingest/{endpoint_id}", json={"body": "hi"},
                          headers={"X-Herald-Ingest-Key": key})
        assert ok.status_code == 201
        r = await c.post(f"/api/ingest-endpoints/{endpoint_id}/revoke")
        assert r.status_code in (200, 204), r.text
        blocked = await c.post(f"/api/ingest/{endpoint_id}", json={"body": "hi"},
                               headers={"X-Herald-Ingest-Key": key})
        assert blocked.status_code == 401


@pytest.mark.asyncio
async def test_messages_list_shows_ingested_message_with_deliveries(app):
    async with await _authed_client(app) as c:
        channel_id = await _create_channel(c, "ch3")
        await c.post("/api/rules", json={
            "name": "r2", "enabled": True, "channel_id": channel_id,
            "filter": {}, "payload_template": {},
        })
        created = (await c.post("/api/ingest-endpoints", json={"name": "ep2"})).json()
        sent = await c.post(f"/api/ingest/{created['endpoint']['id']}",
                            json={"body": "hello world"},
                            headers={"X-Herald-Ingest-Key": created["ingest_key"]})
        assert sent.status_code == 201
        listed = (await c.get("/api/messages")).json()
        assert any(m["body_preview"] == "hello world" for m in listed["messages"])
        assert _run_sql("SELECT count(*) AS n FROM deliveries")["n"] == 1
```

- [ ] **Step 2:** 跑通;渠道/规则响应形状落定后**删掉 `_create_channel` 里的双形状容错,断言固定形状**。全套绿。提交 `git commit -m "test(api): behavioral coverage for authenticated dashboard CRUD"`

### Task 5: 弱测试修正(M8)

**Files:**
- Modify: `backend/tests/test_core.py`、`backend/tests/test_providers.py`、`backend/tests/test_routes.py`、`backend/tests/conftest.py`

- [ ] **Step 1:** `test_core.py` 错误密钥用例替换为(**注意 `_fernet_from_settings` 自带 `@lru_cache`,必须显式清——现测试已有此行,别丢**):

```python
    def test_decrypt_with_wrong_key_fails(self, monkeypatch):
        from cryptography.fernet import Fernet, InvalidToken

        from backend.config import get_settings
        from backend.core import crypto as crypto_mod

        token = crypto_mod.encrypt_json_bytes(b'{"a": 1}')
        monkeypatch.setenv("CHANNEL_CONFIG_ENCRYPTION_KEY", Fernet.generate_key().decode())
        get_settings.cache_clear()
        crypto_mod._fernet_from_settings.cache_clear()
        try:
            with pytest.raises(InvalidToken):
                crypto_mod.decrypt_json_bytes(token)
        finally:
            crypto_mod._fernet_from_settings.cache_clear()  # 不污染后续用例
```

(函数名/是否包装 `InvalidToken` 以 `backend/core/crypto.py` 为准;包装则断言包装类型。)
- [ ] **Step 2:** `test_providers.py` 的 MQTT 成功用例在现有断言后补:

```python
        kwargs = calls["kwargs"]
        assert kwargs["payload"] == b"hello"
        assert kwargs["hostname"] == "broker.example.com"
        assert kwargs["port"] == 1883
        assert kwargs["qos"] == 0
        assert kwargs["retain"] is False
```

(键名以 `backend/providers/mqtt.py` 传给 `paho.mqtt.publish.single` 的实参为准。)同文件私网拒绝用例把 `pytest.raises(Exception)` 收窄为 `from backend.core.ssrf import SSRFError` + `pytest.raises(SSRFError)`。
- [ ] **Step 3:** `test_routes.py` health 用例:`assert response.status_code == 200`、`data["status"] == "ok"`(CI 恒有 Postgres)。
- [ ] **Step 4:** conftest:顶部 `import os`,`TEST_DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://herald:herald@127.0.0.1:5432/herald")`。
- [ ] **Step 5:** 全套绿;提交 `git commit -m "test(backend): tighten weak assertions, honor CI database url"`

### Task 6: 边缘共享加固(M3, M4)

**Files:**
- Modify: `edge/shared/auth.mjs`、`edge/shared/config-cache.mjs`
- Modify: `edge/cloudflare/src/worker.mjs`、`edge/edgeone/edge-functions/[[default]].js`(调用点)
- Test: `edge/tests/shared.test.mjs`(+3 用例)

**Interfaces:**
- Produces:`timingSafeEqualStrings(a, b) -> Promise<boolean>`(任一为空恒 false);`makeConfigLoader` 新语义:`getRaw()` 抛异常时返回热缓存(冷缓存返回 null),不再上抛。

- [ ] **Step 1:** 失败测试(追加到 shared.test.mjs,沿用该文件的 `test`/`assert` 导入):

```js
test("timingSafeEqualStrings", async () => {
  const { timingSafeEqualStrings } = await import("../shared/auth.mjs");
  assert.equal(await timingSafeEqualStrings("secret-token", "secret-token"), true);
  assert.equal(await timingSafeEqualStrings("secret-token", "other"), false);
  assert.equal(await timingSafeEqualStrings("", ""), false);
});

test("makeConfigLoader serves stale cache when getRaw throws", async () => {
  const { makeConfigLoader } = await import("../shared/config-cache.mjs");
  let call = 0;
  const load = makeConfigLoader(async () => {
    call++;
    if (call === 1) return { version: "v1" };
    throw new Error("kv down");
  }, 1000);
  assert.deepEqual(await load(0), { version: "v1" });
  assert.deepEqual(await load(5000), { version: "v1" }); // TTL 过期 + KV 挂 → 用旧值
});

test("makeConfigLoader returns null when cold and getRaw throws", async () => {
  const { makeConfigLoader } = await import("../shared/config-cache.mjs");
  const load = makeConfigLoader(async () => { throw new Error("kv down"); });
  assert.equal(await load(0), null);
});
```

- [ ] **Step 2:** `auth.mjs` 追加:

```js
export async function timingSafeEqualStrings(a, b) {
  const sa = String(a || "");
  const sb = String(b || "");
  if (!sa || !sb) return false;
  // 摘要后比较:等长输入 + 常时比较,消除长度与内容时序信道
  const [da, db] = await Promise.all([sha256Hex(sa), sha256Hex(sb)]);
  return constantTimeEqual(da, db);
}
```

`config-cache.mjs` 的 load 体改:

```js
  return async function load(nowMs = Date.now()) {
    if (cached && nowMs - cachedAt < ttlMs) return cached;
    let raw = null;
    try {
      raw = await getRaw();
    } catch {
      return cached; // KV 抖动不应 500 一个有热缓存的 isolate(stale-on-error)
    }
    if (raw) {
      cached = raw;
      cachedAt = nowMs;
    }
    return cached;
  };
```

- [ ] **Step 3:** 调用点。CF `worker.mjs`:import 行加 `timingSafeEqualStrings`(来自 `../../shared/auth.mjs`);`requireAdmin` 改:

```js
async function requireAdmin(request, env) {
  if (!env.RELAY_ADMIN_TOKEN) return false;
  return timingSafeEqualStrings(bearerToken(request), env.RELAY_ADMIN_TOKEN);
}
```

两处调用改 `if (!(await requireAdmin(request, env)))`。
EdgeOne `[[default]].js`:import 行加 `timingSafeEqualStrings`(来自 `./_shared/auth.mjs`);admin 判定改:

```js
    if (!env.RELAY_ADMIN_TOKEN ||
        !(await timingSafeEqualStrings(bearerToken(request), env.RELAY_ADMIN_TOKEN))) {
      return jsonResponse({ code: "forbidden" }, 403);
    }
```

- [ ] **Step 4:** `npm --prefix edge test` 全绿(现有 admin 403 用例继续通过);提交 `git commit -m "fix(edge): timing-safe admin auth, stale-on-error config cache"`

### Task 7: CF 入口延迟解耦 + 测试缝隙(M2, M9)

**Files:**
- Modify: `edge/cloudflare/src/worker.mjs`(DO `/enqueue` 分支)
- Test: `edge/tests/cloudflare.test.mjs`

**Interfaces:**
- 语义变更:`/enqueue` 只落库 + `setAlarm(now)`,**不再内联转发**;响应恒 `{ok:true}`(删除 `forwarded` 字段——唯一消费者是旧测试,本任务同步改)。首次转发由立即触发的 alarm 完成(新行 `next_attempt_ms = now`,`drainDue(false)` 必选中)。

- [ ] **Step 1:** DO `/enqueue` 分支替换(现 L138-155):

```js
    if (url.pathname === "/enqueue" && request.method === "POST") {
      const e = await request.json();
      const now = Date.now();
      this.ctx.storage.sql.exec(
        "INSERT OR IGNORE INTO pending (id, endpoint_id, received_at, via, ingest_key, body, attempts, next_attempt_ms, last_error, created_ms) " +
          "VALUES (?, ?, ?, ?, ?, ?, 0, ?, NULL, ?)",
        e.id, e.endpoint_id, e.received_at, e.via, e.ingest_key, e.body, now, now,
      );
      // 202 延迟只含一次 SQL 插入;首次转发交给立即触发的 alarm,
      // 上游慢/挂不再拖累发送方(耐久性不变:先落库后应答)。
      await this.ctx.storage.setAlarm(now);
      return Response.json({ ok: true });
    }
```

- [ ] **Step 2:** 测试(cloudflare.test.mjs):
  - 现有 enqueue 相关用例:删除对内联转发/`forwarded` 字段的断言;改断言 `setAlarm` 被调用——若 ctx 桩尚未记录 `setAlarm`,在桩上加 `setAlarm(ts) { this.alarms.push(ts); }`。
  - 路由层 ingest 成功用例补一行:`assert.equal(calls[0].url, "https://do/enqueue");`(防 worker 调用路径与 DO 路由漂移)。
  - 新增 alarm 用例:用现有 FakeSql 预置两行 pending(一行 `next_attempt_ms` 为过去、一行为未来),全局 fetch 桩记录调用;`await buffer.alarm()` 后断言只有到期行被转发、未到期行仍在 pending。
- [ ] **Step 3:** `npm --prefix edge test` 全绿;提交 `git commit -m "perf(edge): decouple ingest 202 from first upstream attempt via immediate alarm"`

### Task 8: EdgeOne 排空重写(F2, M5, M6)

**Files:**
- Modify: `edge/edgeone/edge-functions/[[default]].js`(`drainPending` 重写、`saveOutcome` dead 键、`/admin/status` 分页、两处调用点)
- Test: `edge/tests/edgeone.test.mjs`

**Interfaces:**
- `drainPending(env, {eligible = 20, force = false, skipKey = null})`:cursor 分页扫描(每页 100、至多 5 页),凑满 `eligible` 个**实际处理**的键为止;退避中的键跳过但继续扫描;`force=true` 无视退避。`/relay/drain` 用 `{eligible: DRAIN_BATCH, force: true}`;ingest 的 waitUntil 用 `{eligible: 3, skipKey}`。
- dead 键改死亡时刻:`d_<Date.now()补零16位>_<id32>`;`purgeExpiredDead` 不变即按死亡时刻保留 30 天。
- `/admin/status`:cursor 分页计数(至多 40 页),响应为 `{pending, dead, config_version, oldest_pending_at, truncated}`。
- **前置**:`MemoryKV.list` 需扩展为接受 `{prefix, limit, cursor}` 并返回 `{keys, complete, cursor}`(cursor 可用"下一个起始下标"的字符串);测试文件需从 `[[default]].js` 增加 `drainPending` 的具名 import(它已 `export`)。

- [ ] **Step 1:** 失败测试(追加到 edgeone.test.mjs;**信封时间戳一律取 `Date.now()` 附近**——`drainPending` 的 7 天超龄检查在退避检查之前,1970 时间戳会全部进 dead;新增小助手一并给出):

```js
function makeEnvelope({ id, createdMs, nextAttemptMs = null }) {
  return {
    id, endpoint_id: id, received_at: new Date(createdMs).toISOString(),
    via: "edgeone", ingest_key: "k", body: JSON.stringify({ body: "x" }),
    attempts: 0, last_error: null, created_ms: createdMs,
    ...(nextAttemptMs ? { next_attempt_ms: nextAttemptMs } : {}),
  };
}

function pendingKeyOf(envelope) {
  return `p_${String(envelope.created_ms).padStart(16, "0")}_${envelope.id.replace(/-/g, "")}`;
}

function uid(i) {
  return `${String(i).padStart(8, "0")}-0000-4000-8000-000000000000`;
}

function stubFetch(status = 200) {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return new Response("{}", { status });
  };
  return calls;
}

test("drain skips backoff keys without head-of-line blocking (cross-page)", async () => {
  const kv = new MemoryKV();
  globalThis.EDGE_CONFIG = kv;
  const base = Date.now();
  const future = base + 3600_000;
  for (let i = 0; i < 120; i++) {
    const env = makeEnvelope({ id: uid(i), createdMs: base - 10_000 + i, nextAttemptMs: future });
    await kv.put(pendingKeyOf(env), JSON.stringify(env));
  }
  const eligible = makeEnvelope({ id: uid(200), createdMs: base - 5_000 });
  await kv.put(pendingKeyOf(eligible), JSON.stringify(eligible));
  const calls = stubFetch(200);
  const result = await drainPending({ UPSTREAM_URL: "https://up.example" }, { eligible: 20 });
  assert.equal(result.drained, 1);        // 第二页的可发键被发出
  assert.equal(calls.length, 1);
  assert.equal(result.failed, 0);         // 退避键被跳过,不计 processed
});

test("force drain retries keys still in backoff", async () => {
  const kv = new MemoryKV();
  globalThis.EDGE_CONFIG = kv;
  const env = makeEnvelope({ id: uid(1), createdMs: Date.now() - 1_000, nextAttemptMs: Date.now() + 3600_000 });
  await kv.put(pendingKeyOf(env), JSON.stringify(env));
  const calls = stubFetch(200);
  const result = await drainPending({ UPSTREAM_URL: "https://up.example" }, { eligible: 20, force: true });
  assert.equal(result.drained, 1);
  assert.equal(calls.length, 1);
});

test("dead keys are stamped with death time and purged after 30d", async () => {
  const kv = new MemoryKV();
  globalThis.EDGE_CONFIG = kv;
  const env = makeEnvelope({ id: uid(2), createdMs: Date.now() - 1_000 });
  await kv.put(pendingKeyOf(env), JSON.stringify(env));
  stubFetch(422); // permanent → dead
  await drainPending({ UPSTREAM_URL: "https://up.example" }, { eligible: 5 });
  const deadKeys = (await kv.list({ prefix: "d_", limit: 10 })).keys.map((k) => k.key ?? k.name ?? k);
  assert.equal(deadKeys.length, 1);
  const stamp = Number(deadKeys[0].slice(2, 18));
  assert.ok(Math.abs(stamp - Date.now()) < 60_000); // 死亡时刻,而非创建时刻
  // 时钟前拨 31 天:purge 应清除该键
  const realNow = Date.now;
  try {
    const later = realNow() + 31 * 24 * 3600_000;
    Date.now = () => later;
    stubFetch(200);
    await drainPending({ UPSTREAM_URL: "https://up.example" }, { eligible: 5 });
    assert.equal((await kv.list({ prefix: "d_", limit: 10 })).keys.length, 0);
  } finally {
    Date.now = realNow;
  }
});

test("admin status paginates counts past one page", async () => {
  const kv = new MemoryKV();
  globalThis.EDGE_CONFIG = kv;
  const base = Date.now();
  for (let i = 0; i < 300; i++) {
    const env = makeEnvelope({ id: uid(i), createdMs: base - 300 + i, nextAttemptMs: base + 3600_000 });
    await kv.put(pendingKeyOf(env), JSON.stringify(env));
  }
  await writeConfig(kv);
  const res = await onRequest(context("GET", "/admin/status", { admin: true }));
  const body = await res.json();
  assert.equal(body.pending, 300);         // 单页 256 上限被 cursor 分页跨越
  assert.equal(body.truncated, false);
  assert.ok(body.oldest_pending_at);
});
```

(`MemoryKV`/`context()`/`writeConfig()` 是现文件已有助手,签名以现文件为准微调;`drainPending`、`onRequest` 从 `../edgeone/edge-functions/[[default]].js` import——`drainPending` 需要加入该文件的 import 列表。)
- [ ] **Step 2:** 实现。`[[default]].js` 常量区加:

```js
const DRAIN_SCAN_PAGE = 100;
const DRAIN_SCAN_MAX_PAGES = 5; // 扫描上限 500 键,防子请求预算耗尽
```

`drainPending`(现 L72-104)整体替换:

```js
export async function drainPending(env, { eligible = DRAIN_BATCH, force = false, skipKey = null } = {}) {
  const kv = kvBinding();
  const now = Date.now();
  let drained = 0;
  let failed = 0;
  let dead = 0;
  let processed = 0;
  let cursor = null;
  for (let page = 0; page < DRAIN_SCAN_MAX_PAGES && processed < eligible; page++) {
    const listed = await kv.list({
      prefix: "p_",
      limit: DRAIN_SCAN_PAGE,
      ...(cursor ? { cursor } : {}),
    });
    const keys = (listed?.keys || []).map((k) => k.key ?? k.name ?? k);
    for (const key of keys) {
      if (processed >= eligible) break;
      if (key === skipKey) continue;
      const envelope = await kv.get(key, { type: "json" });
      if (!envelope) continue;
      const createdMs = envelope.created_ms || msFromKey(key);
      let outcome;
      if (now - createdMs > MAX_PENDING_AGE_MS) {
        outcome = { ok: false, permanent: true, error: "max_age_exceeded" };
      } else if (!force && envelope.next_attempt_ms && envelope.next_attempt_ms > now) {
        continue; // 退避中:跳过但继续扫,后面的可发键不被队头阻塞
      } else {
        outcome = await forwardEnvelope(envelope, env.UPSTREAM_URL);
      }
      processed++;
      const saved = await saveOutcome(kv, key, envelope, outcome, now);
      if (saved === "drained") drained++;
      else if (saved === "dead") dead++;
      else failed++;
    }
    if (listed?.complete || !listed?.cursor) break;
    cursor = listed.cursor;
  }
  await purgeExpiredDead(kv, now);
  return { drained, failed, dead };
}
```

`saveOutcome` 的 permanent 分支改(dead 键 = 死亡时刻;`key` 恒为 `p_<16位ms>_<32位id>`,id 起始下标 19):

```js
  if (outcome.permanent) {
    const diedTs = String(now).padStart(16, "0");
    await kv.put(
      `d_${diedTs}_${key.slice(19)}`,
      JSON.stringify({ ...envelope, ingest_key: "[redacted]", last_error: outcome.error }),
    );
    await kv.delete(key);
    return "dead";
  }
```

调用点:ingest waitUntil 改 `drainPending(env, { eligible: 3, skipKey: key })`;`/relay/drain` 改 `drainPending(env, { eligible: DRAIN_BATCH, force: true })`。
`msFromKey` 旁新增分页计数助手,`/admin/status` 块替换:

```js
async function countPrefix(kv, prefix, maxPages = 40) {
  let count = 0;
  let firstKey = null;
  let cursor = null;
  for (let page = 0; page < maxPages; page++) {
    const listed = await kv.list({ prefix, limit: 256, ...(cursor ? { cursor } : {}) });
    const keys = (listed?.keys || []).map((k) => k.key ?? k.name ?? k);
    if (firstKey === null && keys.length) firstKey = keys[0];
    count += keys.length;
    if (listed?.complete || !listed?.cursor) return { count, firstKey, truncated: false };
    cursor = listed.cursor;
  }
  return { count, firstKey, truncated: true };
}
```

```js
    if (url.pathname === "/admin/status") {
      const kv = kvBinding();
      const p = await countPrefix(kv, "p_");
      const d = await countPrefix(kv, "d_");
      const config = await getConfigLoader()();
      return jsonResponse({
        pending: p.count,
        dead: d.count,
        config_version: config?.version ?? null,
        oldest_pending_at: p.firstKey ? new Date(msFromKey(p.firstKey)).toISOString() : null,
        truncated: p.truncated || d.truncated,
      }, 200);
    }
```

- [ ] **Step 3:** 存量测试对齐(同任务内完成,不留红):
  - `MemoryKV.list` 扩展为 `{prefix, limit, cursor}` → `{keys, complete, cursor}`(所有既有调用同步适配)。
  - 既有 drain 用例改新签名 `{eligible, force, skipKey}`。
  - 既有 `/admin/status` 的 `assert.deepEqual` 增加 `truncated: false` 字段。
- [ ] **Step 4:** `npm --prefix edge test` 全绿;提交 `git commit -m "fix(edgeone): cursor-paginated drain without head-of-line blocking, forced drain, death-time dead keys"`

### Task 9: 脚本加固(M1, F4-脚本半, M7)

**Files:**
- Modify: `scripts/sync_edge_config.py`、`scripts/backup_db.sh`、`backend/migrate.py`

- [ ] **Step 1:** sync 推送循环(现 L37-40)替换:

```python
    failures: list[tuple[str, str]] = []
    for edge in [e.strip().rstrip("/") for e in args.edges.split(",") if e.strip()]:
        try:
            _request(f"{edge}/admin/config", admin_token, data=config)
            print(f"pushed version {parsed['version']} -> {edge}")
        except Exception as exc:  # noqa: BLE001 — 每个边缘独立上报,最后统一失败
            failures.append((edge, str(exc)))
            print(f"FAILED -> {edge}: {exc}", file=sys.stderr)
    if failures:
        sys.exit(
            f"config push failed for {len(failures)} edge(s). "
            "Skewed edges 401 new endpoints (permanent dead-letter) — fix and re-run."
        )
```

- [ ] **Step 2:** backup_db.sh 的 dump 段替换:

```bash
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$BACKUP_DIR/herald-$stamp.sql.gz"
# 先写 .tmp,成功才落名:失败绝不留下与好备份同名的截断文件
docker compose exec -T "$COMPOSE_DB_SERVICE" pg_dump -U herald herald \
  | gzip > "$target.tmp"
mv "$target.tmp" "$target"
find "$BACKUP_DIR" -name 'herald-*.sql.gz' -mtime "+$KEEP_DAYS" -delete
find "$BACKUP_DIR" -name '*.sql.gz.tmp' -mtime +1 -delete
echo "backup written: $target"
```

- [ ] **Step 3:** `backend/migrate.py` 的 `apply_migrations`,`try:` 内第一句(建表语句之前)加:

```python
        # 串行化并发迁移(compose migrate 服务 + 手动运行);会话级锁,断开自动释放
        await conn.execute("SELECT pg_advisory_lock(727001)")
```

- [ ] **Step 4:** `pytest backend/tests/test_migrate.py -v` 绿;`bash -n scripts/backup_db.sh` 通过;提交 `git commit -m "fix(scripts): fail-hard config sync, atomic backups, migration advisory lock"`

### Task 10: 文档与部署面(F4-文档半, F5, M10, M11, 威胁模型)

**Files:**
- Create: `.env.example`(仓库根)
- Modify: `.gitignore`(**现有 `.env.*` 规则会忽略 `.env.example`,必须加豁免**)
- Modify: `docs/07_operations.md`、`docs/10_edge.md`、`docs/06_security_privacy.md`
- Modify: `frontend/Dockerfile`(`VITE_API_URL` 默认 8100 → 8000)

- [ ] **Step 1:** `.gitignore`:在 `.env.*` 行后加一行 `!.env.example`。新建 `.env.example`(完整内容):

```bash
# Copy to .env (chmod 600). docker compose reads this file natively —
# interactive shells, systemd, and cron all work without exporting anything.
POSTGRES_PASSWORD=change-me
SECRET_KEY=change-me-32-bytes-min
CHANNEL_CONFIG_ENCRYPTION_KEY=   # python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Optional:
# JWT_SIGNING_KEY=
# EDGE_SYNC_TOKEN=
# CORS_ALLOWED_ORIGINS=https://dashboard.example.com
# FORWARDED_ALLOW_IPS=*
# SENTRY_DSN=
```

验证 `git add .env.example` 不被拒绝。
- [ ] **Step 2:** `docs/07_operations.md`:
  - "Production Compose" 一节的 `export ...` 代码块替换为:复制 `.env.example` → `.env`、`chmod 600 .env`、直接 `docker compose up -d`;注明 compose 原生读取根 `.env`,交互 shell、systemd、**cron(备份脚本)**因此都无需注入环境。
  - 密码重置命令改为生产形式 `docker compose exec api herald-backend reset-password <email>`(uv 形式标注"仅本地开发")。
  - 新增 "Frontend (production)" 一节:

```bash
docker build -t herald-frontend --build-arg VITE_API_URL=https://api.example.com ./frontend
docker run -d --restart unless-stopped -p 3100:3100 herald-frontend
```

  注明容器暴露 3100、`/health` 可作探针、生产建议置于反代/CDN 之后。
- [ ] **Step 3:** `docs/10_edge.md` EdgeOne 一节,在部署命令**之前**补供给步骤:
  1. EdgeOne Pages 控制台创建 KV 命名空间,**绑定到项目、绑定名 `EDGE_CONFIG`**(绑定注入为全局变量,不在 `context.env` 上)。
  2. 项目环境变量设 `UPSTREAM_URL`(Cloudflare Worker 基地址)与 `RELAY_ADMIN_TOKEN`。
  3. 然后 `bash build.sh && npx edgeone pages link && npx edgeone pages deploy`。
  并在 GitHub secrets 说明处注明:`EDGEONE_DRAIN_URL` 是**含路径的完整 URL**,例 `https://edge.example.cn/relay/drain`。
- [ ] **Step 4:** `docs/06_security_privacy.md` 追加一节 "Relay Threat Model Notes"(以下三条全文写入):
  1. 缓冲期内的裸 ingest key:存储转发固有代价——边缘必须原样重放 key。暴露面 = pending 缓冲(Cloudflare DO SQLite / EdgeOne KV),平台静态加密,转发成功即删,dead 记录已脱敏(`ingest_key: "[redacted]"`)。缓解:保持缓冲常态排空;KV/DO 读权限收敛到与 `RELAY_ADMIN_TOKEN` 同级。
  2. 全局 PK 幂等的存在性预言机:认证发送方提交猜测的 UUID,`duplicate:true` 会泄露"该 id 已存在于任何用户"。接受理由:合法 id 为 122-bit 随机 UUIDv4,不可枚举;`user_id` 恒取自认证端点,不存在跨用户读写;故不做按租户拆分的幂等域。
  3. 单 worker 实例假设:僵尸回收(sweep)与多副本并发会造成双投递。部署形态即单实例(compose 单 worker 服务),勿横向扩;需要扩时先给认领行加实例标识。
- [ ] **Step 5:** `frontend/Dockerfile` 的 `ARG VITE_API_URL=http://localhost:8100` 改 `=http://localhost:8000`;`pnpm --dir frontend build` 仍绿。
- [ ] **Step 6:** 提交 `git commit -m "docs(ops): env-file workflow, edgeone provisioning, frontend deploy, threat model"`

### Task 11: 实弹演练与收尾(M12)

- [ ] **Step 1:** 全量回归:三套测试 + `python3 scripts/sync_version.py --check` 全绿。
- [ ] **Step 2:** 生产 compose 冷启动演练(本地):写好根 `.env`(真实随机密钥)→ `docker compose up -d --build` → `curl localhost:8000/health` 为 200/ok → 注册/登录 → 建 ntfy 渠道(`https://93.184.216.34` 之类公网 IP 字面量)→ 建端点与规则 → POST ingest → `docker compose logs worker` 观察投递尝试与退避(目的地不可达 → `retry` 与退避即证明机器转动)。记录输出要点。
- [ ] **Step 3:** kill -9 演练:先打入 ≥5 条消息使 worker 处理中 → `docker kill -s KILL $(docker compose ps -q worker)` → `docker compose up -d worker` → 等 ≤11 分钟 → `docker compose exec db psql -U herald -d herald -c "SELECT count(*) FROM deliveries WHERE status='sending'"` 为 0(僵尸回收生效)。记录输出要点。
- [ ] **Step 4:** 空环境备份演练:`env -i PATH=$PATH HOME=$HOME bash scripts/backup_db.sh` 成功产出 `backups/herald-*.sql.gz`(证明 cron 场景可用)。
- [ ] **Step 5:** 推分支开 PR。PR 描述包含:(a) Step 2–4 演练记录;(b) 未能本地实施项(EdgeOne 真机部署、跨境断链演练)标注为发布前操作员步骤(依赖 ICP 域名与云控制台);(c) 验收清单逐项勾选:

```text
- [ ] 三套测试全绿;后端新增 ≥10 测试,边缘新增 ≥5 测试
- [ ] 限流:同一端点多种写法共享一桶(第三种写法 429);不同端点互不影响
- [ ] EdgeOne:跨页排空发出退避墙后的可发键;force 无视退避
- [ ] priority 3.0 → 201;3.5 → 422
- [ ] .env 就位后 compose 免 export;空环境备份成功
- [ ] 冷启动 / kill -9 演练完成并记录
- [ ] docs/10 含 EdgeOne 供给步骤与完整 drain URL;docs/06 含威胁模型三条;docs/07 含 .env 工作流、前端部署、compose 密码重置
```

---

## Self-Review 检查单

1. **覆盖**:F1→T1,F2→T8,F3→T2,F4→T9+T10,F5→T10,F6→T3,F7→T4;M1→T9,M2→T7,M3/M4→T6,M5/M6→T8,M7→T9,M8→T5,M9→T7,M10/M11→T10,M12→T11。设计 §3 接受项无任务(有意)。
2. **一致**:`timingSafeEqualStrings`(T6 定义,两平台消费);`drainPending` options 签名(T8 定义,同文件两个调用点 + 测试 import 同步);dead 键新格式只被 `purgeExpiredDead`/status 消费(T8 内闭环);`/enqueue` 删除 `forwarded` 字段的唯一消费者是旧测试(T7 同步改);测试时间戳全部取 `Date.now()` 附近(7 天超龄检查在退避检查之前)。
3. **顺序**:T0 先行(建分支 + 提交两份规划文档防丢);T1–T5 后端独立;T6 先于 T7/T8;T9–T11 收尾。按编号执行。
4. 基线漂移处理原则见 Global Constraints 末条;本计划已经过 3 维对抗评审(24 项发现)并全部回修。
