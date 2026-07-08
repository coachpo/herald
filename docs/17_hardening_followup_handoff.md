# Herald 加固复核 —— 收尾修复交接文档

> 版本:1.0(2026-07-08;基线 commit `6fd8325`,分支 `hardening`)
> 读者:执行本文档的开发者。**零上下文可读**,照着做即可,不需要读前面任何设计/计划文档。
> 这是第二轮加固复核发现的收尾清单。前两轮已经落地并通过验证;本文档只处理复核新查出的问题。

---

## 0. 这份文档要你做什么

第二轮加固复核(4 维深审 + 对抗验证)结论:**加固落地真实、完整,7 条验收标准全满足,测试 128+29 全绿。** 但查出 **2 个必须修的问题(A、B)** 和 **6 个建议一起修的小问题(C–H)**。

- **A、B 是拦在"可上线"前的最后两道**,都是几行的小改。
- C–H 是运维体验与健壮性补强,成本都很低,建议一并做完再合并。

全部做完后,这个项目就达到可部署生产环境的标准。

### 每项一句话概览

| 编号 | 严重度 | 一句话 | 改动量 |
|---|---|---|---|
| A | **必修** | 限流的"清理旧桶"逻辑在垃圾流量洪水下会撑爆内存、拖慢每个请求 | middleware.py 改约 8 行 |
| B | **必修** | 生产密钥检查拦不住我们自己发的 `.env.example` 占位符(`change-me`),用它启动 JWT 可被伪造 | config.py 加 2 行 |
| C | 建议 | 反代后面不设 `FORWARDED_ALLOW_IPS` 时,限流会退化(一个人被封=所有人被封) | 文档 1 段 |
| D | 建议 | 没有数据库恢复流程文档,第一次灾难恢复得现编 | 文档 1 段 |
| E | 建议 | API 的 TLS/反代终止步骤没写进 runbook | 文档 1 段 |
| F | 建议 | 测试会读你 shell 里的 `DATABASE_URL` 并清空那个库(可能是你的真库) | conftest.py 改 1 行 |
| G | 建议 | 一段永远走不到的死代码(`uuid.UUID(hex=...)` 分支) | middleware.py 删 3 行 |
| H | 建议 | docs/10 的 `/admin/status` 描述漏了新增的 `truncated` 字段 | 文档改半句 |

---

## 1. 开工准备(一次性)

### 1.1 确认你在正确的位置

```bash
cd /home/qing/Documents/projects/herald
git branch --show-current        # 应输出: hardening
git status --short               # 应为空(干净工作树)
git log --oneline -1             # 应看到: 6fd8325 fix: complete hardening pass
```

如果分支不是 `hardening`,先 `git checkout hardening`。如果工作树不干净,先 `git stash` 或问清楚那些改动是什么再继续。

### 1.2 起本地测试数据库(用于跑后端测试)

```bash
docker start herald-test-pg 2>/dev/null || \
docker run -d --name herald-test-pg \
  -e POSTGRES_DB=herald -e POSTGRES_USER=herald -e POSTGRES_PASSWORD=herald \
  -p 5432:5432 postgres:16-alpine
```

### 1.3 记录基线:三套测试现在应该全绿

```bash
uv run --project backend --locked pytest backend/tests -q        # 期望: 128 passed
npm --prefix edge test                                           # 期望: pass 29 / fail 0
```

（前端不受本文档改动影响,跳过其构建即可。）

如果这一步就有失败,**先停下来**,说明基线本身有问题,不要继续往下改。

---

## 2. 修复 A（必修）：限流清理逻辑的洪水回归

### 2.1 问题是什么（读一遍就懂）

限流器给每个 `(客户端IP, 端点id)` 一个"令牌桶",存在内存字典 `self._buckets` 里。

现在的清理逻辑是:字典超过 1 万条时,删掉"闲置超过 120 秒"的桶。**问题在于**:

1. 攻击者可以用**每次都不一样**的 URL 段刷请求(`POST /api/ingest/垃圾1`、`/api/ingest/垃圾2`……)。这些段不是合法 UUID,代码会原样拿它当桶键(`canonical = segment`),而且这个段最长能到约 16KB。
2. 这些桶全都是"刚刚创建"的,没有一个"闲置超过 120 秒"——所以清理**一个都删不掉**,字典只会一直涨。
3. 更糟:字典一旦超过 1 万条,那句"扫一遍找出要删的"是 O(n) 全表扫描,而且**每个放行的请求都会重跑一次**。稳态下是 `请求速率 × 120 秒` 条(1000 请求/秒 ≈ 12 万条),每条还可能带 KB 级的键文本 → 内存和 CPU 一起被拖垮。

旧代码(本轮修复之前)是"超过 1 万条就整个清空",反而有硬上限。本轮修复把它换成了按时间清理,结果在洪水场景下更差——这是本轮修复自己带进来的回归。

### 2.2 怎么修

两处改动,都在 [backend/middleware.py](../backend/middleware.py)：

**改动 1** — 给垃圾键封顶。找到 `_match` 方法里这段（约在第 126–132 行）：

```python
            try:
                canonical = uuid.UUID(segment).hex
            except ValueError:
                try:
                    canonical = uuid.UUID(hex=segment).hex
                except ValueError:
                    canonical = segment
```

整段替换为（顺便删掉了永远走不到的 `uuid.UUID(hex=...)` 分支，这就是问题 G，一起改了）：

```python
            try:
                # 认证器把同一 UUID 的多种写法(带杠/无杠/大小写/braces/urn)
                # 都规范化成同一个 hex,桶键必须跟着规范化,否则限流可被写法乘法绕过。
                canonical = uuid.UUID(segment).hex
            except ValueError:
                # 非法 UUID(含攻击者构造的垃圾):截断,防止把 KB 级原文塞进桶键。
                canonical = segment[:64]
```

**改动 2** — 清理逻辑加"洪水回退"。找到 `_allow` 方法里这段（约在第 148–153 行）：

```python
        if len(self._buckets) > 10_000:
            cutoff = now - 120.0
            for stale_key in [
                k for k, (_, ts) in self._buckets.items() if ts < cutoff
            ]:
                del self._buckets[stale_key]
```

整段替换为：

```python
        if len(self._buckets) > 10_000:
            cutoff = now - 120.0
            stale = [k for k, (_, ts) in self._buckets.items() if ts < cutoff]
            for stale_key in stale:
                del self._buckets[stale_key]
            # 全新键洪水下没有"闲置"桶可删 —— 硬上限兜底,防止无界增长与 O(n) 扫描。
            if len(self._buckets) > 10_000:
                self._buckets.clear()
```

> 说明:正常流量下桶数远小于 1 万,这两段都不会触发,行为和现在完全一样。只有在被刷时,回退的 `clear()` 会把表清空——极端情况下会误伤当时正在计数的正常用户(令牌被重置),但这远好过整个进程被拖死。这是防滥用的合理取舍。

### 2.3 加一个测试证明它有效

在 [backend/tests/test_middleware.py](../backend/tests/test_middleware.py) **末尾追加**（文件顶部已经有 `pytest` 等 import,不用再加）：

```python
def test_rate_limit_bounded_under_fresh_key_flood():
    """垃圾键洪水下桶表不能无界增长(A 修复的回归守卫)。"""
    from backend.middleware import RateLimitMiddleware

    mw = RateLimitMiddleware(app=None)
    # 灌 20000 个各不相同的键,全部立即放行(每个新键初始令牌满)
    for i in range(20_000):
        assert mw._allow(f"ingest:1.2.3.4:garbage-{i}", 120) is True
    # 洪水回退必须把表压回上限内,而不是留下 2 万条
    assert len(mw._buckets) <= 10_000
```

### 2.4 验证并提交

```bash
uv run --project backend --locked pytest backend/tests/test_middleware.py -q   # 全绿
uv run --project backend --locked pytest backend/tests -q                      # 全套仍 128+ 全绿
git add backend/middleware.py backend/tests/test_middleware.py
git commit -m "fix(ratelimit): bound bucket table under fresh-key flood, cap garbage key length"
```

---

## 3. 修复 B（必修）：生产密钥守卫拦不住模板占位符

### 3.1 问题是什么

生产启动时有个守卫，会在密钥是默认值时拒绝启动。但它只拒 `""` 和 `dev-insecure` 两个值。

本轮我们新发了 [.env.example](../.env.example)，里面写的是 `SECRET_KEY=change-me-32-bytes-min`、`POSTGRES_PASSWORD=change-me`。运维复制这个文件、只填了 compose 强制要求的 `CHANNEL_CONFIG_ENCRYPTION_KEY`、忘了改 `SECRET_KEY`——**服务照样能启动**。而 `SECRET_KEY` 是签 JWT 的密钥,用一个公开在仓库里的值签,任何人都能伪造登录令牌。

docs/07 还恰好写着生产"拒绝默认密钥"——所以这不仅是漏洞,还和文档矛盾。

### 3.2 怎么修

改 [backend/config.py](../backend/config.py)。找到生产守卫这段（约第 111–120 行）：

```python
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

把前两个 `if` 各扩一个条件（拒绝以 `change-me` 开头的模板占位符）：

```python
    if app_env == "production":
        problems = []
        if secret_key in ("", "dev-insecure") or secret_key.startswith("change-me"):
            problems.append("SECRET_KEY must be set to a strong value")
        if jwt_signing_key == "dev-insecure" or jwt_signing_key.startswith("change-me"):
            problems.append("JWT_SIGNING_KEY must not be a default value")
        if not channel_config_encryption_key:
            problems.append("CHANNEL_CONFIG_ENCRYPTION_KEY must be set")
        if problems:
            raise RuntimeError("refusing to start in production: " + "; ".join(problems))
```

### 3.3 加一个测试

在 [backend/tests/test_config.py](../backend/tests/test_config.py) **末尾追加**（该文件已有 `get_settings` 的测试,风格照抄；`_clear` 若不存在就用 `get_settings.cache_clear()`）：

```python
def test_production_rejects_change_me_template_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "change-me-32-bytes-min")
    monkeypatch.setenv("CHANNEL_CONFIG_ENCRYPTION_KEY", "dKkPUi_l6pJiD24yQWhv14jArlTc95xJMu38xpv8uKc=")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        get_settings()
    get_settings.cache_clear()
```

（顶部若还没 `import pytest` / `from backend.config import get_settings`,补上。）

### 3.4 验证并提交

```bash
uv run --project backend --locked pytest backend/tests/test_config.py -q
uv run --project backend --locked pytest backend/tests -q
git add backend/config.py backend/tests/test_config.py
git commit -m "fix(config): reject change-me template secrets in production startup guard"
```

---

## 4. 修复 F（建议）：测试别清空你的真数据库

### 4.1 问题是什么

测试的 conftest 现在这样读数据库地址：

```python
TEST_DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://herald:herald@127.0.0.1:5432/herald")
```

每个测试跑之前会 `TRUNCATE`（清空）所有表。如果开发者用了 direnv/.env、shell 里正好 export 了一个指向**真实或 staging 库**的 `DATABASE_URL`，跑一次 `pytest` 就会静默清空那个库。`DATABASE_URL` 是最容易指向线上库的变量,选它当测试库来源很危险。

### 4.2 怎么修

改 [backend/tests/conftest.py](../backend/tests/conftest.py) 第 15–18 行：

```python
TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://herald:herald@127.0.0.1:5432/herald",
)
```

改成读一个测试专用变量 `TEST_DATABASE_URL`（CI 可以设它；本地不设就用默认）：

```python
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://herald:herald@127.0.0.1:5432/herald",
)
```

### 4.3 CI 也要跟着改

改 [.github/workflows/ci.yml](../.github/workflows/ci.yml)。第 51 行现在是：

```yaml
      DATABASE_URL: postgresql://herald:herald@127.0.0.1:5432/herald
```

在它下面**再加一行**（保留原来的 `DATABASE_URL`,因为 migrate 步骤要用它；新增 `TEST_DATABASE_URL` 给测试用，两者值相同）：

```yaml
      DATABASE_URL: postgresql://herald:herald@127.0.0.1:5432/herald
      TEST_DATABASE_URL: postgresql://herald:herald@127.0.0.1:5432/herald
```

### 4.4 验证并提交

```bash
uv run --project backend --locked pytest backend/tests -q   # 仍全绿(本地默认值没变)
git add backend/tests/conftest.py .github/workflows/ci.yml
git commit -m "test(backend): read TEST_DATABASE_URL so a live DATABASE_URL is never truncated"
```

---

## 5. 修复 C/D/E/H（建议）：文档补强

这几项都只改文档,不改代码,一起做一次提交。

### 5.1 C —— 反代下的限流说明（docs/07）

打开 [docs/07_operations.md](../docs/07_operations.md)，找到环境变量表里 `FORWARDED_ALLOW_IPS` 那一行（第 94 行附近）：

```
| `FORWARDED_ALLOW_IPS` | backend | Trusted proxy IPs passed to uvicorn |
```

把 Notes 一列改成（补一句限流依赖它）：

```
| `FORWARDED_ALLOW_IPS` | backend | Trusted proxy IPs passed to uvicorn. Set this when the API is behind a reverse proxy — otherwise rate limits key on the proxy IP and every sender shares one bucket. |
```

### 5.2 E —— API 的 TLS/反代终止（docs/07）

在 "Production Compose" 一节（第 58 行附近，讲 compose 不跑前端那段之后）加一小段。找到这句结尾：

```
It does not publish the database port and does not run frontend or edge deployments. `EDGE_SYNC_TOKEN` is optional; when unset, `/api/edge-config` returns `404`.
```

在它下面新增一段：

```markdown
The `api` service listens on plain HTTP `:8000`. In production, terminate TLS with any reverse proxy (Caddy, nginx, or Cloudflare) in front of it, then:

- point the proxy at `http://<host>:8000`,
- set `FORWARDED_ALLOW_IPS` to the proxy's IP so client IPs (and rate limits) are honored,
- set `CORS_ALLOWED_ORIGINS` to the dashboard's origin.
```

### 5.3 D —— 数据库恢复流程（docs/07）

找到备份那段的结尾（第 147 行附近，讲 `scripts/backup_db.sh` 的那句之后）：

```
`scripts/backup_db.sh` runs `docker compose exec -T db pg_dump -U herald herald` from the repo root, writes `herald-<timestamp>.sql.gz.tmp`, renames it only after gzip succeeds, and deletes `herald-*.sql.gz` files older than `KEEP_DAYS` (default `14`). The root `.env` used for compose startup also covers cron.
```

在它下面新增恢复流程：

```markdown
Restore from a backup (stop writers first so nothing races the load):

```bash
docker compose stop api worker
gunzip -c backups/herald-<timestamp>.sql.gz | docker compose exec -T db psql -U herald herald
docker compose start api worker
```
```

### 5.4 H —— `/admin/status` 的 truncated 字段（docs/10）

打开 [docs/10_edge.md](../docs/10_edge.md)，找到第 68 行：

```
Admin endpoints require `Authorization: Bearer $RELAY_ADMIN_TOKEN`. `/admin/status` returns pending count, dead count, oldest pending timestamp, and config version. `/relay/drain` returns drained, failed, and dead counts.
```

把 `/admin/status` 那句补上新字段：

```
Admin endpoints require `Authorization: Bearer $RELAY_ADMIN_TOKEN`. `/admin/status` returns pending count, dead count, oldest pending timestamp, config version, and a `truncated` flag that is `true` when the counts exceed the pagination cap. `/relay/drain` returns drained, failed, and dead counts.
```

### 5.5 提交文档改动

```bash
git add docs/07_operations.md docs/10_edge.md
git commit -m "docs(ops): reverse-proxy rate-limit note, TLS termination, restore procedure, truncated field"
```

---

## 6. 全部做完后的最终验证

按顺序跑一遍，全绿才算完成：

```bash
# 后端(需要 herald-test-pg 在跑)
uv run --project backend --locked pytest backend/tests -q        # 期望: 130 passed(128 + A/B 各加 1)

# 边缘
npm --prefix edge test                                           # 期望: pass 29 / fail 0
npm --prefix edge run lint                                       # 无输出即通过

# 版本对齐
python3 scripts/sync_version.py --check                          # 期望: Aligned version: 0.9.0

# 确认没有残留未提交改动
git status --short                                               # 应为空
```

### 逐项自检清单（对照 §0 的表）

- [ ] A：`test_rate_limit_bounded_under_fresh_key_flood` 通过；`middleware.py` 的死分支已删、垃圾键截断到 64、洪水回退 `clear()` 已加
- [ ] B：`test_production_rejects_change_me_template_secret` 通过；`config.py` 守卫拒绝 `change-me` 前缀
- [ ] F：conftest 读 `TEST_DATABASE_URL`；ci.yml 加了 `TEST_DATABASE_URL`
- [ ] C/D/E/H：四处文档改动都在
- [ ] 三套测试 + 版本检查全绿，工作树干净

---

## 7. 交给评审前（PR 描述里要写清楚）

如果你要开 PR，PR 描述请包含以下事实（复核发现的过程偏差，如实记录即可，不用返工）：

1. 本文档修复的 A/B/C/D/E/F/G/H 逐项状态。
2. **既有偏差说明**（上一轮加固的,不是你造成的,但评审会问）：
   - 上一轮加固落成了**单个提交** `6fd8325`,而非计划要求的每任务一提交。
   - `backend/Dockerfile:22` 有一行 `RUN chmod -R a+rX /app`,是上一轮演练时发现的(工作区 umask 077 会让 `COPY . .` 的文件对运行用户不可读),合理但当时没记录——现在补记。
   - 上一轮 kill-9 演练做了时间压缩(手动老化滞留行 + 禁用渠道达到 `sending=0`,而非真等 11 分钟)。已在原 PR 记录。
3. **发布前操作员步骤**(依赖你没有的资源,代码无法覆盖):
   - EdgeOne 真机部署需要 **ICP 备案域名** + EdgeOne Pages 控制台操作(建 KV、绑定 `EDGE_CONFIG`、设 `UPSTREAM_URL`/`RELAY_ADMIN_TOKEN`),步骤见 [docs/10_edge.md](../docs/10_edge.md)。
   - Cloudflare Worker 部署需要 CF 账号 + 在 `wrangler.toml` 填 KV namespace id。
   - 跨境断链演练(停后端 → 两边缘各发 N 条 → 恢复 → 校验零丢失)需要上面两个真机环境才能做。

---

## 8. 不在本文档范围内的事（已知且有意接受，别顺手改）

这些是复核里明确判定"接受不修"的,改它们反而是过度设计:

- 投递成功后 commit 失败的极小概率重发（at-least-once 语义固有,通知场景可接受）。
- 全局消息 id 的"存在性预言机"（合法 id 是 122-bit 随机 UUID,不可枚举；不做按租户拆分的幂等域）。
- 多副本 worker 支持（部署形态就是单 worker,勿横向扩）。
- CF 测试用手写的 `FakeSql`（对未知语句会报错、真实 `RelayBuffer` 类被执行,替换收益低）。

以上四项在 [docs/06_security_privacy.md](../docs/06_security_privacy.md) 的威胁模型和 [docs/15_hardening_design.md](../docs/15_hardening_design.md) §3 都有记录。
