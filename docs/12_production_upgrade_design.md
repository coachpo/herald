# Herald 生产化升级设计文档

> 版本:1.0(2026-07-08)
> 状态:已定稿,配套实施计划见 `docs/13_production_upgrade_plan.md`
> 读者:执行本次升级的开发者(人类或 AI agent)。本文档自包含,不要求读过任何历史讨论。

---

## 0. 上下文交接(必读)

### 0.1 项目是什么

Herald 是**个人自用**的通知网关 monorepo:HTTP 接收结构化 JSON 消息 → 存储 → 按规则转发到 Bark / ntfy / MQTT / Gotify。三个包:

- `backend/` — FastAPI + async PostgreSQL + 后台投递 worker(约 7100 行 Python)
- `frontend/` — React 19 + Vite + React Router 仪表盘
- `edge/` — Cloudflare Worker(当前为 "lite" 直发模式,本次升级将整体重写)

### 0.2 项目所有者的真实目标(本次升级的靠山)

> 个人信息通知网关,能把接收到的消息转发到指定渠道;同时支持 **Cloudflare 与腾讯 EdgeOne 边缘节点部署精简版**。目的是跨国信息流转可用性:在中国大陆收到的消息经中国的 EdgeOne 边缘节点、较少阻碍地传输到境外的 Cloudflare 边缘节点,反之亦然。**EdgeOne 侧要做带存储转发(store-and-forward)的完整版。**

注意:当前仓库文档(`docs/02_architecture.md:95`、`docs/AGENTS.md:68`)含有"禁止把 EdgeOne/代理模式写成现有功能"的历史守卫语句——那是 v1 功能被砍后的文档卫生规则。**本次升级明确恢复并实现该目标,实施计划包含删除这两条守卫。** 执行时不要被这两行吓退。

### 0.3 升级动机:审计结论摘要

2026-07-08 对全仓库做了多维审计(过度设计 / 测试质量 / 生产就绪 / 目标契合),25 项发现经对抗验证确认。分四类:

**A. 开箱即死(必须修)**
1. 无任何邮件发送器,验证 token 生成后只存哈希、原文丢弃(`backend/services/auth_tokens.py:61-93`),但 `backend/services/ingest.py:204` 硬性 403 未验证用户 → **全新部署注册后一条消息都发不进来**。
2. Edge 认证永不匹配:`edge/src/lite.mjs:136` 拿原始 `X-Herald-Ingest-Key` 与后端导出的 HMAC-SHA256 哈希(`backend/edge_config.py:108`)逐字节比较。
3. Worker 崩溃后 `status='sending'` 的行永久卡死(认领查询只选 `queued/retry`,无回收路径,`backend/worker.py:55,72-77`);compose 无 restart 策略。
4. Worker 用单个 AsyncSession 跑 `asyncio.gather` 并发批处理(`backend/worker.py:280-281`),asyncpg 单连接不允许并发操作。

**B. 目标缺口(本次实现)**
5. EdgeOne 零实现;edge 只做 Cloudflare 上的 Bark/ntfy 直发,无中继、无存储转发、无消息回流后端。
6. 配置"同步"是手工 JWT 导出 + 手贴 wrangler 命令;edge 内存缓存无 TTL。
7. KV 快照含解密后的明文渠道凭据(`backend/edge_config.py:117`)。

**C. 过度设计(本次清除,约 -1300 行)**
8. auth 摊在 14 文件约 1270 行;死掉的邮件验证/密码重置装置约 210 行 + 2 张表。
9. 手写 CORS 中间件约 100 行 + 自制 MutableHeaders(`backend/middleware.py:33-104,184-199`)——Starlette 自带纯 ASGI 的 `CORSMiddleware`,手写理由不成立。
10. 369 行手写 DRF 风格验证框架(`backend/services/channel_validation.py`)重造 Pydantic。
11. 三层 re-export 垫片:`backend/models.py`(77 行)、`backend/requests.py`(37 行)、`backend/services/__init__.py`(113 行,零生产消费者)。
12. 死代码与冗余:`backend/auth/jwt.py:59-85 get_verified_user_id`(零调用方)、`backend/core/crypto.py:21-29 encrypt_config/decrypt_config`(仅测试引用)、`backend/auth/tokens.py` 的 `generate_token` 别名(注意:`auth/sessions.py` 有 4 处调用,须先改写调用方再删别名)。
13. 前端:`formState.ts` 195 行纯 useState 管道;`tooltip.tsx` 死代码。

**D. 生产缺口(本次补齐)**
14. 无 schema 迁移(只有 CREATE IF NOT EXISTS);无备份方案;compose 硬编码 dev 密码且 `dev-insecure` 密钥在任何环境静默接受(`backend/config.py:91`);Sentry 只覆盖 API 不覆盖 worker;公网 ingest 与登录无速率限制;镜像 arm64-only;uvicorn 未设 `forwarded_allow_ips`。
15. 测试错配:1394 行后端测试中约 400 行为低价值重复,而 worker(310 行)、ingest 路径(419 行)、登录/刷新/登出流程、MQTT provider 全部零覆盖;CI 起了 Postgres 却没有测试用它。

### 0.4 所有者已拍板的决策

- EdgeOne 做**带存储转发的完整版**,不是 15 行反代。
- **零兼容包袱**:个人项目,不保留数据、不保留 API 兼容、不保留 Django 遗留格式。可以改表名、删表、重建库。
- 其余开放问题按行业惯例决定,原则:不留技术债、不过度设计、干净架构与实现。

### 0.5 平台事实(2026-07 调研,架构依据)

**Cloudflare(免费计划)**
- Workers:100k 请求/天,10ms CPU/次(网络等待不计),128MB 内存,50 子请求/次。
- **Durable Objects:免费计划可用(仅 SQLite 存储后端),支持 alarm**:at-least-once、异常自动重试(2s 起指数退避,至多 6 次)、单对象同时一个 alarm、处理器需幂等。免费额度 100k DO 请求/天、5M 行读/天、100k 行写/天、5GB 存储。**这是免费层上最干净的持久重试原语,选它。**
- Queues:2026-02 起免费层可用,但保留期硬上限 24h、10k ops/天 → 不选(源站宕机超一天即丢消息)。
- KV:写 1000/天、同 key 1 写/秒、跨节点最终一致约 60s → 只用于配置,不用于消息缓冲。
- Cron Triggers:免费可用,账户 5 个 → 不需要(DO alarm 自驱)。
- `waitUntil`:响应后最多 30s,尽力而为、无重试 → 只用于"已持久化之后"的快速转发尝试。

**腾讯 EdgeOne**
- 两种函数产品:站点级"边缘函数"(Service-Worker 风格,**无 KV 绑定**)与 **EdgeOne Pages(Makers)Edge Functions**(`onRequest(context)` 风格,文件路由,**有 KV 绑定**,免费层 KV 1GB)。**选 Pages Edge Functions**(需要 KV)。
- Pages Edge Functions:200ms CPU/次,请求体 ≤1MB,代码包 ≤5MB,`context.waitUntil()` 可用,WebCrypto(`crypto.subtle`)完整可用。
- KV:`put/get/delete/list({prefix,limit≤256,cursor})`;key ≤512B 且字符集仅 `[0-9A-Za-z_]`;value ≤25MB;跨节点最终一致(最多约 60s 陈旧)。**无外部 REST 写 API**(仅控制台)→ 配置写入必须经函数自身的 admin 端点完成。
- **无任何 cron/定时触发器** → 重试排空 = 请求时机会式排空 + 外部定时器(GitHub Actions cron)打 HTTP 排空端点。
- 部署:`edgeone` npm CLI(`edgeone pages deploy`)。
- **ICP 硬约束:要用中国大陆节点,域名必须 ICP 备案**(大陆可用区与含大陆的全球可用区都要;不含大陆的全球可用区不需要)。这是运维前提,代码无法绕过。

### 0.6 术语

- **ingest key**:每个 ingest endpoint 的裸密钥,创建时一次性展示给用户,发送方以 `X-Herald-Ingest-Key` 头携带。
- **token_hash**:后端存储的 HMAC-SHA256(key=SECRET_KEY 或 TOKEN_HASH_KEY)十六进制摘要,用于后端认证。
- **key_sha256**:本次新增,SHA-256(裸 key) 十六进制摘要,专供边缘节点离线认证(边缘可用 WebCrypto 计算 SHA-256,无法计算后端的 HMAC)。
- **envelope(信封)**:边缘缓冲的最小转发单元,见 §3.4。
- **上游(upstream)**:某边缘节点转发的目的地。EdgeOne 的上游是 Cloudflare Worker;Cloudflare Worker 的上游是后端源站。

---

## 1. 目标与非目标

### 1.1 目标(完成即"能部署上线、真正能跑、功能齐全、健壮")

1. 全新部署走文档即可收发消息,无需手工 SQL。
2. 跨境路径可用:CN 发送方 → EdgeOne(CN 节点)→ Cloudflare Worker → 后端;境外发送方 → Cloudflare Worker → 后端。两级边缘均为存储转发:上游不可达时消息持久缓冲、自动重试、最终入库并投递,全程不丢。
3. 消息可靠性:worker 崩溃不丢投递;边缘重试不产生重复投递(幂等);终态可审计。
4. 无明文凭据出库:边缘配置只含 `{id, key_sha256}`,不再导出渠道凭据与规则。
5. 生产姿态:迁移、备份、密钥强制、限流、健康检查、重启策略、双架构镜像、Sentry 全覆盖。
6. 测试覆盖核心路径(worker 状态机、ingest 全路径、auth 会话流、边缘中继),删除低价值重复。
7. 代码净缩减:清除审计确认的约 1300 行过度设计与死代码。

### 1.2 非目标(明确不做,防止范围蔓延)

- **出向中继**(后端经 EdgeOne 反代投递到 CN 内 provider):先直连观察,真有不可达再立项。设计上留扩展点:worker 的 dispatch 全部经 `channel_dispatch.dispatch_channel_message` 单点,将来在该点加 egress 代理即可。
- 边缘本地规则评估与 provider 直发(现 lite 模式):**删除**。边缘只做中继,后端是唯一投递引擎。理由见 §2.2。
- 邮件/SMTP、Prometheus metrics、多实例分布式限流、alembic、管理后台、边缘消息查询 UI。
- 多用户 SaaS 化。保留多用户表结构(改动成本为零)但不为其做任何额外工程。

---

## 2. 架构总览

### 2.1 拓扑

```
发送方(中国大陆)                    发送方(境外)
      │                                   │
      ▼                                   ▼
┌───────────────────┐            ┌──────────────────────┐
│ EdgeOne Pages     │            │ Cloudflare Worker    │
│ Edge Function     │──转发──▶  │  + Durable Object    │
│ (CN 节点, ICP域名)│            │  (SQLite 持久缓冲,   │
│ KV 缓冲 + 机会式  │            │   alarm 自驱重试)    │
│ 排空 + GH cron    │            └──────────┬───────────┘
└───────────────────┘                       │ 转发(原始 ingest key 透传)
                                            ▼
                                 ┌──────────────────────┐
                                 │ Herald 后端(源站)   │
                                 │ FastAPI + PostgreSQL │
                                 │ 幂等 ingest, 存储,   │
                                 │ worker 规则评估+投递 │
                                 └──────────┬───────────┘
                                            ▼
                                  Bark / ntfy / MQTT / Gotify
```

- 后端部署位置由运维决定(典型:境外 VPS,前面可套 Cloudflare 代理)。
- 边缘节点是**入口加速与断链缓冲**,不是第二投递引擎。所有规则评估、渠道投递、历史记录都发生在后端。
- 发送方可以打任意一层:直接打后端、打 CF Worker、或(在 CN)打 EdgeOne。三个入口的请求形状完全一致(`POST /api/ingest/{endpoint_id}` + `X-Herald-Ingest-Key`),行为差异仅是直达返回 201、经边缘返回 202。

### 2.2 关键决策与理由(ADR 摘要)

| # | 决策 | 理由 | 否决的备选 |
|---|------|------|-----------|
| D1 | 边缘只做存储转发中继,删除本地规则评估/Bark/ntfy 直发 | 单一投递引擎(后端)= 单一规则语义、单一重试语义、完整历史;边缘不再需要渠道凭据 → KV 不含明文密钥;删除 JS 版规则/模板引擎及其全部测试,消灭双实现漂移 | 保留 lite 直发:双引擎双语义,KV 装明文凭据,消息不入历史 —— 全是审计确认的缺陷 |
| D2 | CF 侧持久缓冲用 Durable Object(SQLite)+ alarm | 免费层可用、强一致、at-least-once alarm、无保留期上限、退避完全可控、单组件自包含 | Queues:24h 保留上限,断链一天即丢;KV:写配额 1000/天 + 最终一致,做消息队列是错用 |
| D3 | EdgeOne 侧缓冲用 Pages KV + 机会式排空 + GitHub Actions cron 兜底 | EdgeOne 无 DO 等价物、无 cron;KV 是唯一持久原语。幂等上游使最终一致的重复排空无害 | 站点级边缘函数:无 KV 绑定,做不了存储转发 |
| D4 | 边缘认证:后端新增列 `key_sha256 = SHA-256(raw_key)`,边缘用 WebCrypto 计算并常时比较 | 修复"裸 key 对 HMAC 哈希"的死 bug;SHA-256 不可逆,KV 泄露不泄 key(256-bit 随机 token 无字典可撞);边缘无需持有 HMAC 密钥 | 导出 HMAC 密钥到边缘:KV 变成可伪造凭据的钥匙串;直接存裸 key:泄露即失守 |
| D5 | 中继消息认证 = 原始 ingest key 透传,后端照常认证;不设中继专用信任 | 全链路一种认证机制;边缘被攻破也只能重放它见过的 key,不能伪造任意用户消息 | 中继令牌整体信任:一个静态密钥可注入任意端点消息,爆炸半径更大 |
| D6 | 幂等:消息 id 在首个边缘节点铸造(UUIDv4),后端 `ON CONFLICT (id) DO NOTHING` | 重试与重复排空天然无害;全链路一个消息标识可追踪 | 去重表/收据机制:多一张表多一套逻辑,PK 冲突已经免费给出答案 |
| D7 | 缓冲的 envelope 内含裸 ingest key,转发成功即删除 | D5 的直接推论;暴露窗口 = 缓冲时长;CF DO/EdgeOne KV 均平台静态加密;避免为中继发明第二信任路径 | 不存 key 则必须造中继令牌,见 D5 否决理由 |
| D8 | 配置同步:`GET /api/edge-config`(Bearer `EDGE_SYNC_TOKEN` 机器凭据)→ 同步脚本 → 两边缘统一的 `POST /admin/config`(Bearer `RELAY_ADMIN_TOKEN` 平台密钥)写入各自 KV | EdgeOne KV 无外部写 API,admin 端点是唯一通路;两平台同一形状 → 一个脚本、零 wrangler 依赖;机器凭据取代"手工 JWT + 手贴 KV" | wrangler/CF API 直写:只覆盖 CF 一侧,EdgeOne 仍无解 |
| D9 | 删除邮件验证/密码重置装置;注册即可用;`ALLOW_USER_SIGNUP=false` 关闸;密码重置走 CLI | 无 mailer 的验证流是"开箱即死"根因;个人自托管惯例(Gotify/ntfy 同款):不验证邮箱,注册开关 + CLI 重置 | 接 SMTP:引入依赖与配置面,个人部署纯负担 |
| D10 | schema 全部重命名为干净名称(`users`、`messages`…),删除 Django 遗留表/列;编号 SQL 迁移 + 60 行运行器 | 零兼容授权下的一次性偿清;raw SQL 项目用 alembic 是错配(无 ORM 模型可 autogenerate) | alembic:为不存在的 ORM 引入框架 |
| D11 | 限流:进程内令牌桶,纯 ASGI 中间件 | 单实例部署,进程内足够;防的是滥用与爆破,不是精确配额 | Redis/slowapi:为个人部署引入基础设施 |
| D12 | worker 修复:每投递独立 session;认领 batch 后逐个处理;每轮回收超时 `sending` 行 | 修 asyncpg 并发违规与崩溃丢单,两个致命项 | 保单 session 加锁:吞吐无意义(瓶颈在 provider HTTP),复杂度白付 |

### 2.3 消息生命周期(端到端)

以 CN 发送方为例(最长链路):

1. 发送方 `POST https://edge.example.cn/api/ingest/{endpoint_id}`,头 `X-Herald-Ingest-Key: <raw>`,体为 Herald JSON。
2. EdgeOne 函数:查 KV 配置 → SHA-256(raw) 与 `key_sha256` 常时比较 → 校验 payload(格式、大小、字段)→ 铸造 `message_id`(UUIDv4)与 `received_at` → envelope 写入 KV(`p_<毫秒时间戳>_<id去连字符>`)→ **立即返回 202** `{message_id, status:"relayed"}` → `waitUntil`:尝试转发到 CF Worker,成功即删 KV 键;同时机会式排空最多 `list({prefix:"p_", limit:3})` 里的滞留键(跳过本条自身的键)。
3. CF Worker 收到该转发(与直连发送方无差别):同样认证/校验 → envelope 交给 Durable Object。DO 在 SQLite 落库后立即尝试转发后端;失败则 `setAlarm` 按 `min(3600, 5·2^n)` 秒退避重试,直到成功或 7 天后移入 `dead` 表。响应 202。
4. 后端 `/api/ingest/{endpoint_id}`:标准认证(HMAC 比较)→ 读中继头 `X-Herald-Message-Id` / `X-Herald-Received-At` / `X-Herald-Relay-Via`(仅在通过认证后信任;id 必须是合法 UUID,时间戳限 ±48h)→ `INSERT ... ON CONFLICT (id) DO NOTHING`;冲突时返回 200(重复重放),新插入返回 201。规则评估、建 `deliveries` 行照旧。
5. 后端 worker:认领(`FOR UPDATE SKIP LOCKED`)→ 每投递独立 session 串行处理 → provider 分发 → `sent` / 退避 `retry` / 达上限 `failed`。每轮先把 `updated_at` 超过 10 分钟的 `sending` 行扫回 `retry`。
6. 排空兜底:GitHub Actions 每 5 分钟 `POST https://edge.example.cn/relay/drain`(Bearer `RELAY_ADMIN_TOKEN`),排空 EdgeOne KV 滞留;CF 侧 DO alarm 自驱,无需外部触发。

**语义:全链路 at-least-once,后端 PK 幂等收敛为 effectively-once 入库;投递侧 worker 对同一 delivery 行串行重试,不重复投递。** 唯一接受的重复窗口:provider 已收到但响应丢失时 worker 重试 —— 通知场景可接受,与现状一致。

### 2.4 边缘中继协议(规范)

**入口请求(三层一致)**
```
POST /api/ingest/{endpoint_id}
Content-Type: application/json
X-Herald-Ingest-Key: <raw key>
<Herald JSON body ≤ 1 MiB>
```

**边缘 → 上游转发请求**(在入口请求之上追加,body 原样透传):
```
X-Herald-Message-Id: <UUIDv4,首个边缘铸造>
X-Herald-Received-At: <ISO-8601 UTC,首个边缘时钟>
X-Herald-Relay-Via: edgeone | cloudflare | edgeone,cloudflare(逗号追加)
```

**响应**
- 边缘接受:`202 {"message_id": "...", "status": "relayed"}`
- 后端新插入:`201 {"message_id": "..."}`;后端重复:`200 {"message_id": "...", "duplicate": true}`
- 认证失败 401、校验失败 422、超限 413/429 —— 边缘与后端错误码语义一致(边缘在本地就拒绝,坏消息不进缓冲)。

**永久失败与暂时失败**(边缘重试判定):上游返回 400/401/403/404/413/415/422 → 永久失败,进 dead 存储(带 `last_error`),不再重试;网络错误/5xx/超时/429 → 暂时失败,退避重试。(此清单与共享代码 `PERMANENT_STATUSES` 一致,代码为准。)

**envelope 存储格式**(两边缘一致,JSON):
```json
{
  "id": "<uuid4>",
  "endpoint_id": "<uuid>",
  "received_at": "<iso8601>",
  "via": "edgeone",
  "ingest_key": "<raw key>",
  "body": "<原始请求体字符串>",
  "attempts": 0,
  "last_error": null
}
```

**边缘 KV 配置格式**(`config` 键,由 `POST /admin/config` 写入):
```json
{
  "version": "<sha256 前 16 位>",
  "updated_at": "<iso8601>",
  "ingest_endpoints": [ {"id": "<uuid>", "key_sha256": "<hex>"} ]
}
```
边缘函数进程内缓存该配置 **60 秒 TTL**(修复现状的无限缓存)。上游地址不入 KV:它是部署期常量,以平台环境变量/var `UPSTREAM_URL` 配置(CF 为后端基地址,EdgeOne 为 CF Worker 基地址)。

**边缘管理端点**(两平台同形,Bearer `RELAY_ADMIN_TOKEN`,平台级 secret,不入 KV):
- `POST /admin/config` — 写 KV `config` 键(body 即上文 JSON)。
- `GET /admin/status` — `{pending: n, dead: n, config_version, oldest_pending_at}`,供监控与验收。
- `POST /relay/drain` — 排空一批滞留 envelope(EdgeOne 必需;CF 侧也实现,作为 alarm 卡死时的手动兜底)。
- `GET /healthz` — `{ok:true, mode:"relay", platform:"edgeone"|"cloudflare"}`。

### 2.5 密钥与信任边界(升级后全景)

| 密钥 | 所在 | 用途 | 泄露爆炸半径 |
|------|------|------|--------------|
| ingest key(裸) | 发送方;边缘缓冲 envelope(转发成功即删) | 三层入口认证 | 单端点消息注入 |
| `token_hash`(HMAC) | 后端 DB | 后端认证 | 无(不可逆) |
| `key_sha256` | 后端 DB + 边缘 KV 配置 | 边缘离线认证 | 无(不可逆) |
| `SECRET_KEY` | 后端 env | HMAC 密钥、JWT 兜底 | 全后端,生产强制非默认 |
| `CHANNEL_CONFIG_ENCRYPTION_KEY` | 后端 env | 渠道凭据 Fernet 加密 | 渠道凭据(仍只在后端,**不再出库**) |
| `EDGE_SYNC_TOKEN` | 后端 env + 同步脚本 | 拉取 edge-config | 端点 id + key_sha256 清单(低敏) |
| `RELAY_ADMIN_TOKEN` | 两边缘平台 secret + 同步脚本 + GH Actions secret | 边缘 admin/drain | 改边缘配置、触发排空;不能读渠道凭据 |

SSRF 边界不变:渠道 URL 仍在后端保存与投递两处校验(`backend/core/ssrf.py`)。边缘出站 fetch 目的地仅有两个固定值(上游 URL),无用户可控目的地。

---

## 3. 分子系统设计

### 3.1 后端:schema 重建与迁移

新表名(全部重命名,删除 Django 前缀;**删除**两张 token 表与 `email_verified_at`、`is_staff`、`is_superuser` 列):

`users, refresh_tokens, ingest_endpoints, channels, rules, messages, deliveries`

结构性变更点(其余列同现状,完整 DDL 在实施计划 Task 1.2):
- `ingest_endpoints` 新增 `key_sha256 TEXT NOT NULL`(创建时与 `token_hash` 一起从裸 key 派生)。
- `messages` 新增 `relay_via TEXT NULL`(观测跨境路径)。
- `messages.id` 保持 UUID PK —— 幂等锚点。
- 索引沿用现有清单(改名),`deliveries(status, next_attempt_at)` 是 worker 认领热索引,必须保留。

迁移机制:`backend/migrations/0001_initial.sql` 起步的编号 SQL 文件 + `backend/migrate.py` 运行器(约 60 行):`schema_migrations(version, applied_at)` 记账,按序在事务内执行,幂等可重跑。入口 `python -m backend.migrate`。`bootstrap_dev_db.py` 删除,compose/CI/start.sh/文档全部改调 migrate。

### 3.2 后端:auth 收敛

- 删除:`routes/auth_token_routes.py`、`services/auth_tokens.py`、`/resend-verification` 路由、三个对应 schema、两张 token 表、`get_verified_user_id`、ingest 的 `email_not_verified` 门禁。
- 合并:`routes/auth.py` 单文件(signup/login/refresh/logout/me/change-email/change-password/delete-account 八个端点);`services/auth.py` 单文件(吸收 auth_accounts/auth_sessions/auth_shared/auth_users);`auth/` 仅剩 `jwt.py`、`passwords.py`、`sessions.py`、`tokens.py`(删别名)。
- 保留:refresh token 旋转 + family 复用检测(公网登录端点的正经防线);`ALLOW_USER_SIGNUP` 开关(默认 true,建站后关闸)。
- 新增 CLI:`herald-backend reset-password <email>`(生成随机密码打印到终端)——无邮件时代的密码找回。
- 密码哈希:保留现 `pbkdf2_sha256$iter$salt$b64` 实现(纯 stdlib,无依赖),不再声称 Django 兼容。

### 3.3 后端:worker 可靠性

三处修改,全部在 `backend/worker.py`:
1. **认领与处理分离**:认领(短事务,`FOR UPDATE SKIP LOCKED` + 置 `sending`,与现状同)→ 对每个 delivery **开独立 session 串行处理**。删除共享 session 的 `asyncio.gather`。吞吐说明:瓶颈是 provider HTTP(5s 超时),批 50 串行最坏 250s,个人流量无感;真要并发,将来每任务独立 session 即可,已留 `# ponytail:` 注释。
2. **僵尸回收**:每轮轮询开头执行 `UPDATE deliveries SET status='retry', next_attempt_at=now() WHERE status='sending' AND updated_at < now() - interval '10 minutes'`,回收数>0 时记 warning 日志。
3. **可观测**:`delivery_worker()` 启动时调用与 API 共用的 `init_sentry()`(新家 `backend/observability.py`,`app.py` 同步改用);批满时不 sleep(排空积压)。

### 3.4 后端:ingest 幂等与中继头

`services/ingest.py`:
- `create_ingest_message` 支持外部提供的 `message_id`/`received_at`/`relay_via`;INSERT 改 `ON CONFLICT (id) DO NOTHING`,冲突返回 `(message_id, duplicate=True)`,**跳过**规则评估(deliveries 已在首次插入时建好)。
- 中继头校验(认证通过后才读):`X-Herald-Message-Id` 必须 `UUID(raw)` 可解析,否则 422;`X-Herald-Received-At` 必须 ISO-8601 且距今 ±48h,否则忽略用服务器时间;`X-Herald-Relay-Via` 白名单字符过滤,截断 64 字符。
- 删除 `email_not_verified` 门禁(§3.2)。

### 3.5 后端:平台层清理

- `config.py`:`DJANGO_SECRET_KEY`→`SECRET_KEY`;新增 `APP_ENV`(`development` 默认 / `production`)、`EDGE_SYNC_TOKEN`、限流参数、`FORWARDED_ALLOW_IPS`;**`APP_ENV=production` 时启动即拒绝**:`SECRET_KEY` 缺失或等于 `dev-insecure`、`CHANNEL_CONFIG_ENCRYPTION_KEY` 为空、`JWT_SIGNING_KEY` 等于默认值 → `RuntimeError` 快速失败;裸 `float()` 换安全解析。
- CORS:删手写 `CorsMiddleware` 与 `MutableHeaders`,一行 `starlette.middleware.cors.CORSMiddleware`(纯 ASGI,与 asyncpg 任务绑定约束不冲突;该约束继续禁止 `BaseHTTPMiddleware`,在 middleware.py 模块 docstring 保留说明)。
- 渠道验证:`services/channel_validation.py`(369 行)→ `schemas/channel_configs.py` Pydantic 模型(每渠道一个 + SSRF 校验,约 120 行);错误细节直接从 pydantic `errors()` 的 `loc` 扁平映射为 `{"config": {<字段或 non_field_errors>: [消息]}}`,**不保留** DRF 风格文案与字段编码约定(核实:前端只渲染 `error.message`,无人消费字段级结构,旧形状不是契约)。
- 删除垫片与死代码(§0.3 C 类清单全部)。
- 限流:`RateLimitMiddleware`(纯 ASGI,进程内令牌桶):`POST /api/ingest/*` 按 endpoint_id 桶(默认 120/分),`/api/auth/login|signup|refresh` 按 IP 桶(默认 10/分),超限 429 + `Retry-After`。
- `cli.py`:`uvicorn.run(..., proxy_headers=True, forwarded_allow_ips=<env>)`。

### 3.6 边缘:Cloudflare Worker + Durable Object

文件:`edge/cloudflare/wrangler.toml`、`edge/cloudflare/src/worker.mjs`(fetch 入口 + `RelayBuffer` DO 类)、共享逻辑 `edge/shared/*.mjs`(auth/validate/envelope/config,两平台复用)。

- fetch 入口:路由 `/healthz`、`/admin/*`、`/relay/drain`、`/api/ingest/{id}`。ingest 流程:KV 配置(60s 内存 TTL)→ sha256 认证 → payload 校验 → envelope → `RELAY_BUFFER` DO(`idFromName("global")` 单例)`/enqueue` → 202。
- DO `RelayBuffer`(SQLite):表 `pending`(envelope 各字段 + `next_attempt_at`)与 `dead`;`/enqueue` 插入后**只对本条**立即尝试转发(积压排空绝不阻塞入口响应),失败置退避并 `setAlarm`;`alarm()` 处理到期行(单批上限 25 条——免费层每次调用 50 个子请求硬限,留余量):成功删行、永久失败移 `dead`、暂时失败退避翻倍(`min(3600s, 5·2^n)`)重设 alarm;超 7 天(以入缓冲时间 `created_ms` 计)移 `dead`;`dead` 保留 30 天后清除。alarm 处理器幂等(at-least-once 语义 + 后端 PK 幂等兜底)。
- 绑定:KV `EDGE_CONFIG`(仅配置),DO `RELAY_BUFFER`;secret `RELAY_ADMIN_TOKEN`;var `UPSTREAM_URL`(后端基地址)。
- 删除:`lite.mjs`、`rules.mjs`、`template.mjs`、`providers.mjs`、`cloudflare-worker.mjs` 及其全部测试。

### 3.7 边缘:EdgeOne Pages Edge Function

文件:`edge/edgeone/edge-functions/[[default]].js`(单函数全路由)+ 复用 `edge/shared/`(若 EdgeOne 打包器拒绝越目录 import,则构建时复制共享文件进 `edge-functions/`,实施计划含验证步骤)。

- 同一路由集、同一认证/校验/信封逻辑。差异仅存储与重试:
  - envelope → KV:键 `p_<入缓冲epoch毫秒左补零16位>_<id去连字符>`(满足 `[0-9A-Za-z_]` 字符集且按时间字典序);envelope 内记录 `created_ms`(入缓冲时刻);7 天超龄与键序都以 `created_ms` 为准(**不用** sender 可控的 `received_at`,与 CF DO 语义一致);dead → `d_` 前缀,排空时顺带清除 30 天前的 `d_` 键。
  - 返回 202 后 `context.waitUntil()`:转发本条(成功删键)+ 机会式排空 `list({prefix:"p_", limit:3})` 中最老的滞留键(跳过本条自身)。
  - `/relay/drain`:每次处理至多 20 键(留足 fetch 子请求余量),返回 `{drained, failed, dead}`。
  - `/admin/status` 的 `oldest_pending_at` 从首个 `p_` 键的毫秒前缀解析(list 字典序即时间序)。
  - 重试计数与 `last_error` 写回 envelope(KV 覆盖写);永久失败条件同 §2.4;滞留超 7 天移 `d_`。
- 绑定:**KV 命名空间以绑定名注入为全局变量 `EDGE_CONFIG`(EdgeOne Pages 的 KV 不在 `context.env` 上,`context.env.EDGE_CONFIG` 是 undefined)**;`context.env` 仅承载普通环境变量 `RELAY_ADMIN_TOKEN`、`UPSTREAM_URL`(指向 CF Worker)。
- 兜底排空:`.github/workflows/edge-drain.yml`,`schedule: '*/5 * * * *'`,对 EdgeOne 的 `/relay/drain` 发 POST(secrets:`EDGEONE_DRAIN_URL`、`RELAY_ADMIN_TOKEN`)。GitHub cron 尽力而为(可能延迟),与机会式排空互为补充,可接受。
- **运维前提(文档必须写明)**:CN 节点要求 ICP 备案域名;无备案则只能用"全球可用区(不含中国大陆)",跨境增益退化。

### 3.8 配置同步

- 后端 `GET /api/edge-config`:改为 Bearer `EDGE_SYNC_TOKEN` 认证(env 未设置时端点直接 404);导出形状见 §2.4(不再含 channels/rules;**全体用户**的活跃端点,不再按当前登录用户过滤)。
- `scripts/sync_edge_config.py`(stdlib urllib,零依赖):拉后端 → 对每个配置的边缘 URL `POST /admin/config`。用法:
  `python scripts/sync_edge_config.py --backend https://api.example.com --edges https://relay.example.com,https://edge.example.cn`
  (token 经 env `EDGE_SYNC_TOKEN`/`RELAY_ADMIN_TOKEN` 传入)。端点增删后手动跑一次,或挂 GH Actions;60s TTL 缓存保证最迟一分钟生效。

### 3.9 运维与交付

- compose(生产姿态,根 `docker-compose.yml`):secrets 用 `${VAR:?required}` 强制注入、db 不发布端口、全服务 `restart: unless-stopped`、api healthcheck(`curl -f /health`)、worker `restart` + 依赖 db 健康、json-file 日志 max-size。开发另立 `docker-compose.dev.yml`(现有默认值搬过去),`start.sh` 改用之。
- `backend/Dockerfile` 加 `HEALTHCHECK`;`docker-images.yml` 平台改 `linux/amd64,linux/arm64`。
- `scripts/backup_db.sh`(`pg_dump | gzip` + 保留 14 天)+ 文档 cron 行。
- Sentry:`backend/observability.py` 统一初始化,API 与 worker 都调用。
- 文档:重写 README、`02_architecture.md`、`06_security_privacy.md`、`07_operations.md`、`10_edge.md`(中继协议)、`openapi.yaml`;删除 `11_edge_lite_feasibility.md`;**删除 `docs/AGENTS.md:68` 与 `docs/02_architecture.md:95` 的 EdgeOne 禁令**;各包 AGENTS.md 同步。

### 3.10 前端

- 删除:`ResetPasswordForm.tsx`、`VerifyEmailClient.tsx`、`ForgotPasswordPage.tsx`、router 三条路由、LoginForm 的忘记密码链接、AccountPage 的验证状态区与 resend 按钮、SignupPage 验证文案、`types.ts` 的 `email_verified_at`、五个页面的 `canCreate/canMutate/canDelete` 验证门禁(改为恒可用)。
- 简化:`formState.ts` 195 行 → 每渠道一个 `useState<object>`(约 30 行);删 `tooltip.tsx` 与 `main.tsx` 的 `TooltipProvider`。
- 不新增页面(边缘状态用 `curl /admin/status`,YAGNI)。

### 3.11 测试策略

- **后端新增**(全部走 CI 已有的真实 Postgres;conftest 提供 schema 迁移 + 每测试 TRUNCATE + 工厂函数):
  `test_worker.py`(退避纯函数、认领互斥、三个终态路径、retry→failed 转换、僵尸回收、幂等重放),`test_ingest_api.py`(401/413/415/400/422/201 全路径、中继头、重复 200、限流 429),`test_auth_flows.py`(注册→登录→me→旋转→复用检测→登出→改密吊销全家),`test_migrate.py`,`test_channel_configs.py`(pydantic 模型,承接原 test_services 用例),`test_core.py` 补规则 6 个缺口用例(与被删的 JS 版对齐),`test_providers.py` 补 MQTT provider(stub paho 客户端:发布成功、连接失败、SSRF 拦截)。
- **修剪**:8 个 401 检查合并为一个 parametrize;Gotify/ntfy priority 复制块 parametrize;删无断言的 `test_health_not_access_logged`;SSRF 测试 monkeypatch `socket.getaddrinfo` 断网可跑。OpenAPI schema 断言**保留**(前端手写类型的唯一契约防护)。
- **边缘**:`node --test` + 手写 KV/DO/fetch 桩(维持零依赖);覆盖认证、校验、缓冲落库、立即转发成功/失败、drain、永久失败进 dead、admin 端点鉴权。两平台共享逻辑测一份,平台差异各测存储层。
- CI:后端 job 先跑 `python -m backend.migrate`(替换 bootstrap);edge job 改指向新测试。

---

## 4. 验收标准(整体 DoD)

1. 全新机器按 `docs/07_operations.md` 从零部署(compose 起后端 + wrangler 部署 CF + edgeone 部署 EdgeOne + 同步配置),不执行任何文档外命令,完成:注册 → 建渠道/端点/规则 → 分别向三个入口(后端、CF、EdgeOne)POST 消息 → 三条均到达 provider 且仪表盘历史各有一条、无重复。
2. 断链演练:停掉后端 30 分钟,期间向 CF 与 EdgeOne 各发 N 条 → 全部 202;恢复后端 → 10 分钟内全部入库并投递,条数精确等于 N+N,零丢失零重复(`/admin/status` pending 归零)。
3. 杀死演练:worker 处理中 `kill -9` → 重启后 10 分钟内无永久 `sending` 行,消息最终 `sent`。
4. `APP_ENV=production` + 缺失/默认密钥 → 进程拒绝启动并打印明确错误。
5. `pytest backend/tests -v` 全绿(CI 的 Postgres 真实参与);`npm --prefix edge test` 全绿;`pnpm --dir frontend lint && build` 通过。
6. 后端源码行数较升级前净减 ≥ 800 行(过度设计清除的下限验证)。
7. 仓库无任何 `TODO`/`FIXME` 新增;无 `email_verified`、`beacon_`、`accounts_`、`DJANGO_` 残留引用(grep 验证)。

---

## 5. 风险与开放项

| 风险 | 应对 |
|------|------|
| EdgeOne Pages 免费层边缘函数请求/CPU 配额未公开(调研 UNCONFIRMED) | 个人流量极小;实施时用 `edgeone pages dev` 实测;超限则升个人版(¥,量级可忽略) |
| EdgeOne 打包器对 `edge/shared/` 越目录 import 的支持未确认 | 实施计划 Task 3.1 先行验证;失败则构建脚本复制共享文件(已写入计划) |
| GitHub Actions cron 延迟(尽力而为,可能 3-10 分钟) | 与机会式排空互补;EdgeOne 断链窗口内新请求也会触发排空;可接受 |
| DO 单例吞吐上限(单对象串行) | 个人流量;将来可按 endpoint_id 分片 `idFromName(endpoint_id)`,协议不变 |
| KV 缓冲最终一致导致 drain 短暂看不到新键 | 幂等上游使重复/迟见无害;7 天窗口远大于 60s 陈旧 |
| ICP 备案是行政流程,非代码可解 | 文档明示;无备案时的降级路径(全球不含大陆区)也写入运维文档 |
