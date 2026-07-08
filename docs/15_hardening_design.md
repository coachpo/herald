# Herald 加固更新设计(第二轮)

> 版本:1.2(2026-07-08;基线 commit `08eb0df`)
> 配套实施计划:`docs/16_hardening_plan.md`(自包含,可独立执行)。
> 读者:执行本轮修复的开发者,零上下文可读。

---

## 0. 背景

第一轮生产化升级已全部落地(commit `b51ce77..5f6e1fc`,文档收编 `08eb0df`):后端 118 测试、边缘 21 测试、前端构建全绿。落地后做了 6 维深审(15 个验证 agent,发现均经对抗复核),**确认 8 项 major、27 项 minor,无 blocker**。本轮修 major 全部 + 高价值 minor,其余明确接受并记录(§3)。

注意:仓库文档已做过收编(一次性的升级计划/验证文档已删除,内容并入 `docs/07`、`docs/10` 等长期文档)。本设计与配套计划是**当前仅有的两份规划文档**,执行完毕后同样可删,验收证据记录在 PR 描述中。

## 1. 修复范围与技术决策

### 1.1 Major(全修)

| # | 问题(复检确认,含证据位置) | 决策 | 理由 |
|---|---|---|---|
| F1 | ingest 限流可绕过:桶键用原始 URL 段(`backend/middleware.py` `_match`),而认证器接受同一 UUID 的带杠/无杠/大小写/braces/urn 多种写法 → 每种写法一个独立桶;且限流在认证**前**消耗、endpoint id 非秘密(edge 配置内含),第三方可饿死指定租户的桶;`_buckets` 超 1 万条全表 `clear()` 连带清掉所有人的限流状态 | 桶键改 **`ingest:{客户端IP}:{UUID规范hex}`**(段无法解析成 UUID 时按原文);淘汰改为**剔除闲置 >120s 条目**,不再全清 | per-IP-per-endpoint:垃圾流量只烧自己 IP 的桶,租户正常发送不受影响;规范化消灭多写法乘法 |
| F2 | EdgeOne 排空队头阻塞:`drainPending` 只 `list` 字典序最老的 N 键、不用 cursor 分页,退避中的键占满窗口 → 断链恢复后全部投递最长停摆 1 小时;`/relay/drain` 无强制语义(`edge/edgeone/edge-functions/[[default]].js`) | 重写:**cursor 分页扫描**(每页 100、至多 5 页),凑满 `eligible` 个实际处理的键为止;`/relay/drain` 传 **`force=true` 无视退避**(对齐 CF `drainDue(true)`) | 分页消灭队头阻塞;force 让 GH cron 兜底真正兜底;500 键扫描上限防子请求预算耗尽 |
| F3 | 校验平价缺口:`{"priority": 3.0}` 边缘(JS)判整数放行 → 202 后后端(Python)判 float → 422 → 永久死信,发送方无感知(`edge/shared/validate.mjs` vs `backend/services/ingest.py`) | **后端归一整值 float**:`3.0 → 3` 后再校验(priority 是 payload 唯一 int 字段) | 单点修复覆盖三个入口;边缘与协议不动 |
| F4 | 备份 cron 必失败:`docker compose exec` 触发 compose 插值,`${POSTGRES_PASSWORD:?}` 在 cron(无环境)直接 fail;pg_dump 失败还残留截断的 .gz(`scripts/backup_db.sh`) | 文档化**仓库根 `.env`**(compose 原生读取,交互 shell/cron/重启一体生效,chmod 600;提供 `.env.example`);脚本改**写 `.tmp` 成功后 `mv`** | .env 是 compose 官方机制;tmp+mv 保证备份要么完整要么不存在 |
| F5 | EdgeOne 供给步骤缺文档:无"创建/绑定 KV 命名空间、设两个环境变量"步骤,照文档部署得到 fail-closed 死中继;`EDGEONE_DRAIN_URL` secret 需含完整路径这一点未写明 | `docs/10_edge.md` EdgeOne 节补控制台步骤 + drain URL 说明 | 纯文档 |
| F6 | worker 状态机测试缺口:失败→`retry` 退避转换(最常见生产路径)、`channel_disabled`、`message_not_found` 终态无测试 | 补 3 个测试。`message_not_found` 经数据无法构造(FK 级联 + worker 消息查询不过滤 `deleted_at`),改为**直接调用 `process_delivery`** 并伪造指向不存在消息的认领行 | 该分支是防御性代码,直测函数是唯一确定性路径 |
| F7 | 认证后 CRUD API 零行为测试(全靠 401 检查与 OpenAPI 断言) | 补 4 个 happy-path 测试(建渠道→列表;建规则;建+撤销端点+撤销后 401;ingest 后消息列表含投递行) | 复用现有 fixtures,边际成本极低 |

(复检的第 8 项 major 与 F1 同根因,并入 F1。)

### 1.2 并入的 minor

| # | 问题 | 决策 |
|---|---|---|
| M1 | `sync_edge_config.py` 部分推送失败 → 配置偏斜 → 新端点消息在旧配置边缘 401(**永久死信**) | 每边缘独立 try;任一失败**非零退出**并列出失败边缘;成功的照常推(收敛优先于原子) |
| M2 | CF ingest 的 202 与首次上游转发串行(DO `/enqueue` 内 `await this.forward`),上游慢时拖累发送方 | `/enqueue` 只 INSERT + `setAlarm(now)`,转发全部交给立即触发的 alarm;202 延迟 = 一次 SQL 插入;耐久性不变(先落库后应答) |
| M3 | 两边缘 admin token 用 `===` 比较(时序侧信道) | shared 增 `timingSafeEqualStrings`(双方 SHA-256 摘要 + 现有常时比较),两平台改用 |
| M4 | `makeConfigLoader` 的 KV 读异常直接抛 → 有热缓存也 500 | getRaw 抛异常时**回落热缓存**(stale-on-error);冷缓存返回 null(入口按 misconfigured 500,行为同现状) |
| M5 | EdgeOne dead 记录保留期从**信封创建时刻**起算(键沿用 `p_` 时间前缀) | dead 键改用**死亡时刻**:`d_<diedMs补零16位>_<id>`;purge 逻辑不变即正确 |
| M6 | EdgeOne `/admin/status` 计数被 `limit:256` 截断 | cursor 分页计数(至多 40 页),响应增 `truncated` 字段 |
| M7 | 迁移运行器无跨进程互斥 | `pg_advisory_lock(727001)` 会话锁(断开自动释放,2 行) |
| M8 | 四处弱测试:错误密钥解密实测密钥格式错误;MQTT 不断言 payload/qos;health `in (200,503)` 永真;conftest 硬编码 DATABASE_URL | 逐个修正(第二把合法 Fernet 密钥 + `InvalidToken` + **同时清 `_fernet_from_settings` 的 lru_cache**;断言 paho kwargs;health 断死 200/ok;`os.environ.get("DATABASE_URL", <默认>)`) |
| M9 | CF 测试缝隙:DO stub 不校验 `/enqueue` 路径;`alarm()`/非强制排空零调用 | 补路径断言 + alarm 测试(一到期一未到期,只发到期者) |
| M10 | 生产前端部署无文档;`frontend/Dockerfile` 的 `VITE_API_URL` 默认 8100 对不上后端 8000 | docs/07 补前端生产一节;Dockerfile 默认改 8000 |
| M11 | 密码重置文档命令在生产 compose 下连不上库(db 不发布端口) | 文档改 `docker compose exec api herald-backend reset-password <email>` |
| M12 | 第一轮 DoD 演练以测试引用替代实弹 | 收尾任务本地实弹:生产 compose 冷启动、worker `kill -9`;结果记入 PR 描述 |

## 2. 威胁模型补记(写入 docs/06,全文见实施计划 Task 10)

1. **缓冲期内的裸 ingest key**:存储转发固有代价——边缘必须原样重放 key。暴露面 = pending 缓冲(CF DO SQLite / EdgeOne KV),平台静态加密,转发成功即删,dead 记录已脱敏。缓解:保持缓冲常态排空;KV/DO 读权限收敛到与 `RELAY_ADMIN_TOKEN` 同级。
2. **全局 PK 幂等的存在性预言机**:认证发送方提交猜测的 UUID,`duplicate:true` 泄露"该 id 存在于任何用户"。接受:合法 id 为 122-bit 随机 UUIDv4 不可枚举;`user_id` 恒取自认证端点,无跨户读写;不做 per-tenant 幂等域。
3. **单 worker 实例假设**:僵尸回收(sweep)与多副本并发会双发。部署形态即单实例(compose 单 worker),勿横向扩;需要扩时先给认领行加实例标识。

## 3. 明确不修(接受项)

- **投递成功后 commit 失败的重发**:at-least-once 固有,通知场景可接受。
- **幂等域按租户拆分**:见 §2.2。
- **CF 测试的 FakeSql**:已存在、对未知语句 fail-loud、真实 `RelayBuffer` 类被执行;替换收益低于成本,保留。
- **多副本 worker 支持**:见 §2.3。
- **auth 限流的代理健壮性**:`FORWARDED_ALLOW_IPS` 开关已存在并有文档,不改代码。

## 4. 验收标准

1. 三套测试全绿;后端新增 ≥10 个测试,边缘新增 ≥5 个。
2. 限流:同一 endpoint 的 dashed/dashless/大写路径共享同一桶(第三种写法直接 429);不同 endpoint 互不影响。
3. EdgeOne 排空(单测):第一页 100 个退避键 + 第二页 1 个可发键 → 非强制排空发出该键;`force` 无视退避重试。
4. `{"priority": 3.0}` 直连后端 → 201;`3.5` → 422。
5. 根 `.env`(600 权限)就位后:`docker compose config` 无需 shell export;`env -i PATH=$PATH HOME=$HOME bash scripts/backup_db.sh`(模拟 cron 空环境)成功产出备份。
6. 实弹演练完成并记录于 PR 描述:生产 compose 冷启动 → 注册 → ingest → 投递尝试;worker 处理中 `kill -9` → 重启 → ≤11 分钟无残留 `sending` 行。
7. `docs/10` 含 EdgeOne 完整供给步骤与 `EDGEONE_DRAIN_URL` 完整 URL 说明;`docs/06` 含 §2 三条威胁模型;`docs/07` 含 .env 工作流、前端生产部署、compose 形式的密码重置。
