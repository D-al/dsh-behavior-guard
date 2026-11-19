# 一致性守卫设计：防三副本漂移 + 防"文档宣称完成但没生效"

> 版本：2026-11-20 ｜ 状态：设计稿（未实现）｜ 约束：零 LLM、低开销、只读设计
> 目标：把今晚事故里的教训固化成确定性、可自动触发、能自证运行过的守卫，不依赖人记得跑、不依赖 35B 判断。

---

## 0. 设计约束与实测基线

### 0.1 硬约束
- 零 LLM：所有判据是文件存在/内容匹配、sha256、git 元数据、JSON 字段、单测退出码、trace 行统计。绝不调用 35B（每步 11s，8G 显存全留给推理）。
- 低开销：离线全量守卫目标 < 2s（十来个文件 sha256 + 几条 git 命令）；运行时哨兵 < 5ms（几次小文件 read + append）。
- 失败可见：守卫自身出错必须 exit 2（而非静默 exit 0）；"没证据"必须落到 UNKNOWN/FAIL，不许等价成 PASS。

### 0.2 本次探查确认的基线事实（设计依据）
| 事实 | 位置 / 取值 | 含义 |
|---|---|---|
| 权威源 A(本地) | D:/Brain/publish/dsh-behavior-guard，HEAD de9d111，分支 main | 唯一可写源 |
| 远端 A(remote) | https://github.com/D-al/dsh-behavior-guard.git | git ls-remote 可比 commit |
| 运行版 C | D:/Brain/dsh-data/profiles/desktop/node_modules/* | dsh 真正加载的副本 |
| autostart 权威/运行版 | 权威 v1.2.0(HEAD 7926407) / 运行版 v1.1.1 | 活的漂移样本 |
| harness 版本/CHANGELOG | package.json=2.26.2 / CHANGELOG 顶部 2.26.5 | 版本声称与机器版本不一致 |
| CRLF | git config core.autocrlf = true | 必须做规范化 sha，否则假差异 |
| 权威块 | ROADMAP.md 第 12-422 行 <!-- ROADMAP_GRAPH_BEGIN v1 --> ... <!-- ROADMAP_GRAPH_END -->，YAML，schema_version: 1 | 状态唯一真相源 |
| 镜像 | CAPABILITY_LADDER.yaml（语义字段 + status 副本） | 非真相源，需校验漂移 |
| 写入器 | tools/roadmap_check.py：load_ladder()/save_authoritative()/cmd_apply() | 目前无校验签名 |
| 证据资产 | tools/test_*.mjs、_trace.jsonl 按 kind + sid、_audit_feedback.jsonl、_agent_harness_loaded.json、git diff | 交叉验证素材 |
| 反灌水白名单 | 权威块 test_sids：s1, outcome-, budget-1..4, b7332eb6, r, fb, b, inject-test | trace 必须排除 |
| 哨兵可复用点 | autostart index.mjs 的 dbg()（写 llama-debug.log）与 apply()；frame_limiter.py 的 --release-all / 父进程看门狗 | 见 §6 |
| CI / hooks | 无 CI 配置；.git/hooks/* 全是 .sample，无激活钩子 | 强制触发点只能靠本地钩子 + 自读循环 |
| 证据阶梯 | docs/POSTMORTEM_20261120.md L1-L5 | 交叉验证必须到 L4/L5 |

---

## 1. 总体架构

```
                +----------------------------------------------------------+
                |  tools/consistency_guard.py  (总入口, exit 0/1/2)           |
                |    --scope copies|claims|signature|all                    |
                |    --json <bench/_guard_report.json>                      |
                |    --strict  --quiet(哨兵模式)                            |
                +-------+--------------+--------------+----------+
                        |              |              |
              +---------v------+ +-----v--------+ +---v------------+
              | 1. 三副本比对   | | 2. 宣称vs落地 | | 3. 签名/写回纪律|
              | collect_copy() | | claim_audit.py| | verify_integrity|
              | compare()      | | (复用check_one)| | (roadmap_check)|
              +---------+------+ +-----+--------+ +---+------------+
                        |              |              |
                        +----- 统一 REPORT + diff 清单 -----+
                                       |
         +-----------------------------+-----------------------------+
         | 强制触发点(§7)               |                              |
   pre-commit / pre-push hook    roadmap_check.py --next 前置    release 写 CHANGELOG 前置
         |
   +-----v------------------------------------------+
   | 4. 运行时哨兵(§6)                                |
   | autostart apply() -> sentinel()                 |
   |   -> dbg() + _guard_sentinel.jsonl              |
   | harness probe -> _agent_harness_loaded.json.guard |
   +------------------------------------------------+
```

统一报告结构（所有子检查共用，便于机器消费与失败归因）：

```json
{
  "ts": "2026-11-20T...", "head": "de9d111", "verdict": "PASS|FAIL|UNKNOWN",
  "checks": [
    {"id":"copies.commit.A_eq_B", "status":"PASS|FAIL|EXEMPT|SKIP|UNKNOWN",
     "expected":"de9d111", "actual":"...", "detail":"..."}
  ],
  "diffs": [{"scope":"copies", "field":"version", "a":"1.2.0", "c":"1.1.1"}],
  "exit_code": 0
}
```

判定优先级：ERROR(工具自身坏) > FAIL > UNKNOWN > EXEMPT/SKIP > PASS。--strict 把 UNKNOWN/EXEMPT 也升级为 FAIL。

---

## 2. 一致性守卫脚本 tools/consistency_guard.py

### 2.1 三份拷贝的精确定义（先定"谁算生产"）

| 代号 | 路径 | 角色 | 是否纳入生产比对 |
|---|---|---|---|
| A-remote | git ls-remote origin HEAD / refs/heads/main | 远端真相 | 是（commit 级，离线可用） |
| A-local | D:/Brain/publish/dsh-behavior-guard（+ autostart 同构） | 权威源，唯一可写 | 是（commit + 文件 sha + version） |
| C-runtime | D:/Brain/dsh-data/profiles/desktop/node_modules/{dsh-behavior-guard,dsh-llama-server-autostart} | dsh 实际加载 | 是 |
| 副本/缓存 | node_modules/.pnpm/**、pnpm store（~/.local/share/pnpm/store）、D:/WorkBuddyWorkSpace/**/dsh-* 旧 clone | 缓存 / 外星 clone | 否（只做 INFO，不参与 PASS/FAIL） |

硬规则：pnpm store 与旧 clone 永不作为比对基准，也不作为"权威"候选。对旧 clone 只检查一件事——它的 git remote -v 若指向同一 origin 且 HEAD 落后，报 INFO(stale clone) 而非 FAIL，防止有人把它当权威改。

### 2.2 关键资产清单 config/GUARD_MANIFEST.yaml

不硬编码文件名，用清单驱动（改清单需走 §4 的签名）：

```yaml
schema: 1
repos:
  - id: harness
    authoritative: D:/Brain/publish/dsh-behavior-guard
    runtime: D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-behavior-guard
    remote: https://github.com/D-al/dsh-behavior-guard.git
    key_files: [package.json, index.mjs, cordis.patch.yml, ROADMAP.md,
                CAPABILITY_LADDER.yaml, tools/roadmap_check.py, tools/frame_limiter.py]
    version_field: package.json:version
  - id: autostart
    authoritative: D:/Brain/publish/dsh-llama-server-autostart
    runtime: D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-llama-server-autostart
    key_files: [package.json, index.mjs, frame_limiter.py, cordis.patch.yml]
    version_field: package.json:version
normalize: lf            # sha256 前统一 \r\n -> \n
exempt_link_junctions: true   # pnpm link: 的 junction 是标准机制
non_production_paths:
  - node_modules/.pnpm/
  - pnpm-store
  - D:/WorkBuddyWorkSpace/
```

### 2.3 核心函数与伪代码

```python
# —— CRLF 假差异消除（core.autocrlf=true 是本次实测配置）——
def sha256_normalized(path: Path) -> str:
    b = path.read_bytes()
    b = b.replace(b'\r\n', b'\n').replace(b'\r', b'\n')   # 两边同规范化
    return hashlib.sha256(b).hexdigest()

def sha256_git_blob(repo: Path, ref: str, rel: str) -> str:
    # git 对象库存的是 LF；用同一规范化函数处理，保证与工作树可比
    b = subprocess.run(['git','show',f'{ref}:{rel}'], cwd=repo,
                       capture_output=True, timeout=10).stdout
    return hashlib.sha256(b.replace(b'\r\n', b'\n')).hexdigest()

# —— junction 识别（link: 依赖属正常例外，但不能盲跳）——
def reparse_target(path: Path):
    # Windows: ctypes GetFileAttributesW + FILE_ATTRIBUTE_REPARSE_POINT
    # 或读重解析点 Target；返回 (is_junction, target)
    ...

# —— 采集一份拷贝 ——
def collect_copy(role, root, manifest) -> dict:
    out = {'role': role, 'root': str(root)}
    out['commit'] = git(root, 'rev-parse', 'HEAD') if is_git_repo(root) else None
    out['version'] = read_json_field(root / manifest.version_field)
    out['files'] = {p: sha256_normalized(root/p) for p in manifest.key_files if (root/p).exists()}
    out['junctions'] = []
    if role == 'runtime':
        for p in walk_one_level(root):
            is_j, tgt = reparse_target(p)
            if is_j:
                allowed = (manifest.exempt_link_junctions and 'node_modules' in str(p)
                           and ('.pnpm' in tgt or 'publish' in tgt))
                out['junctions'].append({'path':str(p),'target':tgt,
                                         'status':'EXEMPT(link-junction)' if allowed else 'FAIL'})
    out['lock_commit'] = parse_lock_commit(root)   # pnpm-lock.yaml 中 git/url commit 或 stamp commit
    return out

# —— 比对 A/B/C ——
def compare(a_remote, a_local, c_runtime, manifest):
    checks = []
    # 1) commit：A-remote == A-local（ls-remote，不 fetch，低开销）
    checks.append(ck('copies.commit.remote_eq_authoritative',
                     a_remote['commit'] == a_local['commit'],
                     a_remote['commit'], a_local['commit']))
    # 2) 运行版 commit 必须匹配其自带 GUARD_STAMP.json（见 §5）
    stamp = read_json(c_runtime/'GUARD_STAMP.json')
    checks.append(ck('copies.commit.runtime_stamp',
                     bool(stamp) and stamp['commit'] == c_runtime['commit_stamp'],
                     a_local['commit'], stamp and stamp.get('commit')))
    # 3) version：A-local == C；并单列 CHANGELOG 顶部版本声称
    checks.append(ck('copies.version.authoritative_eq_runtime',
                     a_local['version'] == c_runtime['version'],
                     a_local['version'], c_runtime['version']))
    changelog_ver = parse_changelog_top(manifest.authoritative/'CHANGELOG.md')
    checks.append(ck('copies.version.changelog_eq_package',
                     changelog_ver == a_local['version'], changelog_ver, a_local['version']))
    # 4) 关键文件 sha（规范化后）
    for p in manifest.key_files:
        checks.append(ck(f'copies.sha.{p}',
                         a_local['files'].get(p) == c_runtime['files'].get(p),
                         a_local['files'].get(p), c_runtime['files'].get(p)))
        if a_local['commit']:
            checks.append(ck(f'copies.sha.git_blob.{p}',
                             a_local['files'][p] == sha256_git_blob(a_local['root'],'HEAD',p),
                             'worktree', 'HEAD'))
    checks += [ck(f'copies.junction.{j["path"]}', j['status']=='EXEMPT(link-junction)',
                  'link: exception', j['status']) for j in c_runtime['junctions']]
    return checks
```

### 2.4 网络退化与防抖
- git ls-remote 超时/失败 -> UNKNOWN(remote unreachable)，不判 PASS 也不崩，由 --strict 决定是否阻断（默认 warn）。
- sha 比对先做文件大小快速比较，字节数不同直接 FAIL，省去大文件读。
- 所有外部命令带 timeout，捕获 FileNotFoundError（缺依赖）-> exit 2 + 明确错误。
- 报告写 BENCH_DIR/_guard_report.json，同时 stdout 人类可读摘要；--quiet 只输出 exit code 给钩子/sentinel 用。
---

## 3. "宣称 vs 落地"交叉验证 tools/claim_audit.py

核心原则（针对历史坑）：不用关键词计数。代码里出现字符串 != 文件在权威源 != 真的跑了 != 真实会话命中。每条"完成 X"声明必须携带结构化 expect，且必须出现至少一条 L4/L5 证据才允许 PASS。

### 3.1 结构化声明（在 CHANGELOG 条目里内嵌，人不可见部分机器可读）

```markdown
## [2.26.5] - 2026-11-20（能力阶梯按调研修正）
<!-- CLAIM_BEGIN
- id: C-2.26.5-1
  text: 权威源归一到 ROADMAP 内嵌块
  expect:
    - {kind: file_grep, path: tools/roadmap_check.py, regex: ROADMAP_GRAPH_BEGIN, min: 1}
    - {kind: git_diff_nonzero, from: v2.26.4, to: HEAD, paths: [ROADMAP.md, tools/roadmap_check.py]}
    - {kind: trace_count, source: _trace.jsonl, kind_name: evidence_cited,
       sid_filter: exclude_tests, min: 1}
  alt_sources: []
-->
```

- parse_claims(changelog_text) 从 CLAIM_BEGIN/END 解析。
- 无结构化块的普通 bullet -> UNVERIFIED，绝不 PASS（直接堵死"关键词计数把内存变量当落盘"）。
- 允许 doc_only: true（纯文档声明）和 by_design_off: true（如 S4 adaptive_route=0），各有专门判据。

### 3.2 复用已有 verify 原语，零重复实现

claim_audit.py 直接 import roadmap_check 并复用 check_one(v, data)/load_ladder()/resolve_path() —— 已有 kind：file_exists/file_grep/test_pass/trace_count/trace_absent/json_field/gate_result/manual。新增两个 kind 供 claims 专用：

```python
def check_one(v, data):        # 在 roadmap_check.py 中扩展（仍零 LLM）
    ...
    if kinds == 'git_diff_nonzero':
        stat = git('diff','--stat', f'{v["from"]}..{v["to"]}', '--', *v['paths'])
        # 仅 *.md 改动对代码声明不算数
        code_lines = sum(n for f,n in parse_stat(stat) if f.endswith(('.py','.mjs','.ps1','.yml')))
        return code_lines > 0, f'code_lines={code_lines}'

    if kinds == 'artifact':
        p = resolve_path(v['path'])
        if v.get('field'): return check_json_field(p, v)   # 复用 json_field 逻辑
        return p.exists() and p.stat().st_size >= v.get('min_bytes',1), str(p)
```

### 3.3 证据分级映射（对齐 POSTMORTEM 的 L1-L5）

| expect kind | 证据级别 | 能证明 |
|---|---|---|
| file_exists / file_grep | L1 | 写了 |
| test_pass / gate_result | L2 | 隔离环境逻辑对 |
| json_field / artifact + git_diff_nonzero | L5 | 独立产物落地 + 代码真改 |
| trace_count / trace_absent（带 sid_filter: exclude_tests） | L4 | 真实会话触发 |

### 3.4 判定规则（把历史坑逐条编码成硬门）

```python
def verdict(claim, results, data):
    # 门 1：没有 expect -> UNVERIFIED（关键词计数陷阱）
    if not claim.expects: return 'UNVERIFIED'
    # 门 2：代码声明却没有代码 diff -> FAIL（v2.26.1 "0 行代码"陷阱）
    if not claim.doc_only and not any(e.kind=='git_diff_nonzero' and e.ok for e in results):
        return 'FAIL: no_code_diff'
    # 门 3：任何 trace_count 缺 sid_filter -> UNVERIFIED（89% 假数据陷阱）
    for e in claim.expects:
        if e.kind in ('trace_count','trace_absent') and e.get('sid_filter') != 'exclude_tests':
            return 'UNVERIFIED: unfiltered_trace'
    # 门 4：file_* 路径必须落在权威 ROOT，bench/ 是运行数据不能证明代码落地
    #       （CHANGELOG 说修 weakness_miner.py 但权威 tools/ 没有 -> 这里 FAIL）
    for e in claim.expects:
        if e.kind in ('file_exists','file_grep') and resolve_path(e.path) is under BENCH_DIR:
            return 'FAIL: evidence_not_in_authoritative'
    # 门 5：到 L4/L5 才算真完成；只有 L1/L2 -> UNVERIFIED（不许以 L1/L2 冒充）
    levels = {e.level for e in results if e.ok}
    if not (levels & {'L4','L5'}):
        if claim.doc_only: return 'PASS(doc_only)' if all(e.ok for e in results) else 'FAIL'
        return 'UNVERIFIED: only_L1_L2'
    # 门 6：零证据辨析——先查 alt_sources（写别处 / 设计关闭 / 没触发）
    if any(e.kind=='trace_count' and not e.ok for e in results):
        for alt in claim.alt_sources:      # 例如 _audit_feedback.jsonl
            if evidence_present(alt): return 'PASS(alt_source)'
        if claim.by_design_off: return 'PASS(by_design_off)'   # trace_absent max:0
        return 'FAIL: no_real_trace'
    return 'PASS' if all(e.ok for e in results) else 'FAIL'
```

### 3.5 与权威块 done 状态互证

遍历权威块中 status: done 的 item：
- evidence_log 必须非空、每条含 commit 与 checks；缺任一 -> FAIL(fake_done)（对应既有"done 必须携带 commit+命令+退出码"设计）。
- evidence_log[].commit 必须能在 git log 找到；找不到 -> FAIL（防伪造/回填）。
- done 但 verify 全 PASS 却无任何 trace/artifact 类判据 -> UNVERIFIED 提示（可能是纯结构项）。

输出 BENCH_DIR/_claim_audit.json，逐条声明列 id | verdict | evidence_level | evidence，供人复核与 §6 钩子读取。
---

## 4. 写回纪律：唯一写入口 + 校验签名

目标：--apply 只写权威块；任何手工改字段（今晚新加字段被改坏）在读取时立刻报警。

### 4.1 权威块加 integrity 段（schema_version 升 2，向后兼容 v1 只读告警）

```yaml
schema_version: 2
block_id: roadmap-graph
integrity:
  algo: sha256
  payload: <HEX>          # canonical_payload 的 sha256
  prev: <HEX|null>        # 上一版 payload 哈希，构成哈希链
  written_by: tools/roadmap_check.py@de9d111
  written_at: 2026-11-20T02:15:00Z
# ... 原 items/rungs/anchors/status_enum/test_sids ...
```

### 4.2 规范化与校验（确定性，可在任何机器复算）

```python
def canonical_payload(graph: dict) -> bytes:
    g = {k:v for k,v in graph.items() if k != 'integrity'}   # 排除 integrity 自身
    return yaml.safe_dump(g, allow_unicode=True, sort_keys=True).encode('utf-8')

def compute_checksum(graph) -> str:
    return hashlib.sha256(canonical_payload(graph)).hexdigest()

def verify_integrity(md_text):
    graph = parse_block(md_text)
    integ = graph.get('integrity')
    if not integ:                      # 老块未签名
        return 'LEGACY'                # warn；--strict 视为 FAIL，给迁移命令
    got = compute_checksum(graph)
    if got != integ['payload']:
        drift = field_diff(reconstruct_expected(graph), graph)  # 逐字段列出被改项
        raise IntegrityError(f'权威块被手工改动: {drift}')       # 阻断所有命令
    return 'OK'
```

load_ladder() 第一步调用 verify_integrity(md_text)；IntegrityError 时除 --show-drift（只打印差异）外所有子命令拒绝执行。这样"手工改坏字段"在 --next 那刻就爆出来，而不是等 agent 爬卡时静默用错数据。

### 4.3 唯一写入口（收敛所有写操作）

- 现状：save_authoritative() 已被 cmd_claim/cmd_apply 共用——保持并强化。
- 改造：save_authoritative(data, reason, actor) 是唯一允许写 ROADMAP.md 权威块的函数；内部三步：
  1. 写前 verify_integrity 必须 OK（已被改坏则拒绝覆盖，避免把损坏固化）；
  2. 重算 integrity.payload、integrity.prev = 旧 payload、写 written_by/written_at；
  3. 同步镜像 CAPABILITY_LADDER.yaml 的 status，并写入 mirror_of: <payload>。
- 新增 tools/roadmap_edit.py：唯一受支持的"手工字段编辑"CLI。白名单只允许改 status/verify/deps/risk/notes，走同一 save_authoritative 自动重签。文档/技能明令禁止直接编辑 ROADMAP.md 权威块（编辑即校验失败）。
- 哈希链校验：consistency_guard.py --scope signature --chain-depth 30 遍历改过 ROADMAP 的 commit，逐版重算 payload 并验证 prev 链——检测"抹掉 integrity 段 / 回填旧签名"。

### 4.4 镜像漂移
对每个 item 比对权威块 status 与 CAPABILITY_LADDER.yaml 同名 item 的 status，以及镜像的 mirror_of == 权威 payload。不一致 -> FAIL(mirror_drift)（默认 FAIL 而非 WARN，因为今晚教训就是镜像被当真相）。

---

## 5. 运行时哨兵：dsh 启动时自报"加载版本 vs 权威"

复用现有 dbg() 与 _agent_harness_loaded.json 探针，不新增依赖、不改启动关键路径（绝不 throw —— !!js 事故证明硬失败代价更高）。

### 5.1 发布时打桩 GUARD_STAMP.json

consistency_guard.py stamp 在权威源生成，随 setup/install*.ps1 拷到 node_modules：

```json
{"schema":1, "commit":"7926407", "version":"1.2.0",
 "generated_at":"...", "files":{"package.json":"<sha>", "index.mjs":"<sha>", "frame_limiter.py":"<sha>"}}
```

这是 §2 离线比对（完整 hash）与 §5 运行时比对（只看 commit+version，便宜）之间的桥。

### 5.2 autostart index.mjs 的 sentinel（在 apply() 内，dbg('apply called') 之后调用）

```js
function guardSentinel() {
  const here = __dirname
  const pkg = JSON.parse(fs.readFileSync(path.join(here, 'package.json'), 'utf8'))
  const stamp = readIfExists(path.join(here, 'GUARD_STAMP.json'))
  const authDir = process.env.DSH_AUTHORITATIVE_DIR || 'D:/Brain/publish/dsh-llama-server-autostart'
  let auth = { version: null, commit: null }
  try {
    auth.version = JSON.parse(fs.readFileSync(path.join(authDir, 'package.json'),'utf8')).version
    auth.commit  = readIfExists(path.join(authDir, 'GUARD_STAMP.json'))?.commit || null
  } catch (e) { /* 权威不可达 -> UNKNOWN，绝不当 MATCH */ }
  const loaded = { version: pkg.version, commit: stamp?.commit ?? null }
  let verdict = 'UNKNOWN'
  if (auth.version && loaded.version && auth.version === loaded.version &&
      (!auth.commit || auth.commit === loaded.commit)) verdict = 'MATCH'
  else if (auth.version) verdict = 'DRIFT'
  const rec = { ts: new Date().toISOString(), verdict, loaded, authoritative: auth, path: here }
  dbg('[SENTINEL] ' + verdict + ' loaded=' + loaded.version + '@' + (loaded.commit ?? '?') +
      ' auth=' + (auth.version ?? '?') + '@' + (auth.commit ?? '?') + ' path=' + here)  // 复用 llama-debug.log
  try { fs.appendFileSync(path.join(BENCH_DIR, '_guard_sentinel.jsonl'), JSON.stringify(rec)+'\n') } catch {}
  return rec   // 非致命：永不 throw
}
```

要点：
- fail-safe：权威不可达 / stamp 缺失 -> UNKNOWN/DRIFT，不判 MATCH（"没证明一致" != "一致"）。
- _guard_sentinel.jsonl 同时是"哨兵真的运行过"的 L4 证据（§6 元守卫会查最近 N 次会话是否有记录）。
- GUARD_SENTINEL_MODE=warn|block 默认 warn；block 也只注入一条 steer 提示，不阻止启动。

### 5.3 harness 探针补 guard 字段

index.mjs 第 738 行现写 {loadedAt, version:2, config}——注意 version:2 是探针 schema 不是包版本（易被误读）。新增同文件小函数 guardStamp()（读自身 package.json + 同目录 GUARD_STAMP.json，与权威对比），把结果写进探针：

```js
writeFileSync(cfg.probePath, JSON.stringify({
  loadedAt: ..., version: 2,
  guard: { pkgVersion, buildCommit, authoritative: {version, commit}, verdict },
  config: cfg }, null, 2))
```

这样 _agent_harness_loaded.json 既是"插件被加载"的 L3 证据，也是"加载版本/commit 与权威一致"的 L4 证据。
---

## 6. 失败模式清单（守卫自身会怎么失效）+ 强制触发点

### 6.1 失效模式与对策

| # | 失效模式 | 后果 | 对策 |
|---|---|---|---|
| F1 | 守卫从没被运行（无 CI、无钩子、没人手动跑） | 形同虚设 | §6.2 四重强制触发点；尤其 --next 前置（agent 每次自读必过） |
| F2 | 守卫文件本身过期/被改（复制旧版、改成恒 PASS） | 假绿 | selfcheck：自身 sha256 与 config/GUARD_SELF_PIN.txt（单独 commit 固定）比对，不符 -> FAIL |
| F3 | 在错误的仓库跑（Workspace 旧 clone） | 查错目标还 PASS | collect_copy 校验 git remote -v 必须等于清单 remote，否则 exit 2 |
| F4 | 缺依赖/命令失败被吞成 0 | 静默通过 | 所有外部调用捕获异常 -> exit 2 + 错误串；缺 yaml -> 明确报错 |
| F5 | 报告写了没人读 | 漂移无人知 | 报告生成同时打印摘要；钩子把 FAIL 挡在 commit/push；--next 打横幅 |
| F6 | 环境变量劫持（BENCH_DIR/DSH_AUTHORITATIVE_DIR 指向假权威） | 绕过比对 | 清单写死权威绝对路径；env 仅允许覆盖 BENCH_DIR，覆盖权威需 --allow-auth-override 且记入报告 |
| F7 | CRLF/junction 假差异 -> 告警疲劳 -> 被关闭 | 守卫被禁用 | §2.3 规范化 sha + junction 明确 EXEMPT 且验证 target；假差异绝不进 FAIL |
| F8 | 网络不可用 ls-remote 失败 | 崩溃或假绿 | 退化为 UNKNOWN(remote unreachable)，由 --strict 决定阻断，绝不 PASS |
| F9 | 守卫自己写它审计的文档 | 自我认证循环 | 守卫只读 CHANGELOG/ROADMAP；唯一写入口是 roadmap_check.py，两者权限分离 |
| F10 | test_sids 白名单被改小以吞假数据 | 89% 假 trace 复活 | test_sids 位于权威块内，受 §4 签名保护；改动触发 IntegrityError |
| F11 | stamp 过期/被删 | sentinel 假 MATCH | stamp 含 generated_at + commit，与当前 HEAD 不符 -> UNKNOWN；文件缺失 -> DRIFT |
| F12 | 报告缓存复用（读到上次 PASS） | 假绿 | 报告必须带 head 与当前 git rev-parse HEAD 相等才算 fresh，否则重算 |

### 6.2 强制触发点（相互独立，任一层漏了还有下一层）

1. 本地 git hooks（首选，当前无 CI）：setup/install.ps1 安装 .git/hooks/pre-commit（跑 --scope signature,claims --strict --quiet，FAIL 阻断）与 pre-push（跑 --scope copies --include-remote 全量）。钩子脚本本身也纳入 selfcheck。
2. roadmap_check.py --next 前置硬门：agent 每次自读能力阶梯选卡前，先跑 --scope signature --quiet；签名 FAIL -> 打印"权威块被改坏，先修复"并 exit 非 0，agent 无法继续爬卡。这是唯一随每次 agent 会话自动触发的点，弥补无 CI。
3. 发布纪律：写新 ## [x.y.z] / cmd_apply 前，assert_fresh_guard_report(head) 检查 BENCH_DIR/_guard_report.json 的 head == 当前 HEAD 且 verdict==PASS；不满足拒绝写。把"守卫跑过且绿"变成发版硬前置。
4. 运行时哨兵：每次真实 dsh 启动都写 _guard_sentinel.jsonl；元守卫检查最近 N 次会话是否有 sentinel 记录——没有则守卫/插件没被正确加载（F1 的检测器）。
5. 可选 CI：若接 GitHub Actions，.github/workflows/guard.yml 在所有 push/PR 跑 --all --strict；但不能依赖它（当前没有，且硬件约束在本地）。

### 6.3 成本预算
- 离线全量：sha256（约 12 个文件）+ 4 条 git 命令 + 解析 2 个 JSON + 读 CHANGELOG/ROADMAP ≈ < 2s。
- --next 前置：仅 signature（读 ROADMAP + 算一次 sha256）≈ < 50ms。
- 运行时 sentinel：读 2 个小 JSON + 2 次 append ≈ < 5ms/启动。
- 全程 0 次 LLM 调用，不影响 35B 推理。

---

## 7. 落地顺序（建议，本设计不含实现）

1. roadmap_check.py：加 verify_integrity / integrity 段 / save_authoritative 重签 / roadmap_edit.py（§4）——地基（签名保护 test_sids）。
2. consistency_guard.py 先做 copies + signature 两个 scope（§2、§4.4），跑通真实漂移样本（autostart 1.2.0 vs 1.1.1、harness 2.26.2 vs 2.26.5 应判 FAIL）。
3. claim_audit.py + CHANGELOG 的 CLAIM_BEGIN 模板（§3），先给 v2.26.5 一条声明做样板。
4. GUARD_STAMP.json + autostart sentinel + harness probe 扩展（§5）。
5. setup/install.ps1 装 hooks + roadmap_check.py --next 前置门 + 发布 assert（§6.2）。

## 8. 验收标准（本设计是否达成的判据）
- [ ] 当前两处真实漂移能被守卫判 FAIL 并列出差异（autostart 版本、harness 版本）。
- [ ] 手工改权威块任一字段后，--next/--dry-run 立即 IntegrityError，且逐字段列出改动。
- [ ] 一条"完成 X"但只有 file_grep 证据的声明 -> UNVERIFIED（不是 PASS）。
- [ ] trace_count 不带 sid_filter 的声明 -> UNVERIFIED；带 s1 假数据的 trace 不被计为真实命中。
- [ ] git diff --stat 0 行代码的"代码修复"声明 -> FAIL: no_code_diff。
- [ ] autostart 启动后 llama-debug.log 有 [SENTINEL] 行且 _guard_sentinel.jsonl 有对应记录；把运行版 stamp 改成旧 commit -> 报 DRIFT。
- [ ] 全链路 0 次 LLM 调用；离线守卫实测 < 2s。