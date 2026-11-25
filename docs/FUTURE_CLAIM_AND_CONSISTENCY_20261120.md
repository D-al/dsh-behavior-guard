# 未来断言与一致性守卫（2026-11-20）

> FUTURE_CLAIM_GUARD 设计+分析、一致性设计与裁决、DIAGNOSIS_CORRECTION、GAP_REVIEW

> 本卷合并 6 份原报告（2026-11-25 整理）。

## 本卷目录

- `FUTURE_CLAIM_GUARD_20261120.md`（原文件保留为引用桩）
- `FUTURE_CLAIM_GUARD_ANALYSIS_20261120.md`
- `CONSISTENCY_GUARD_DESIGN_20261120.md`
- `CONSISTENCY_VERDICT_20261120.md`
- `DIAGNOSIS_CORRECTION_20261120.md`
- `GAP_REVIEW_20261120.md`

---

## 原报告：`FUTURE_CLAIM_GUARD_20261120.md`

## 将来时承诺守卫（A1_6，2026-11-20）

> 根因：A1_5 推卡时 agent 输出"现在进入核心：编写 check_verify.py"后结束回合、文件不存在。
> 守卫 L0-L3 全漏——L1 的 `WRITE_CLAIM` 只认过去时（已写入/已创建），
> 将来时（现在写/接下来创建）能过 L3 的长度门槛又不触发 L1 的路径校验。

### 1. 设计：把将来时承诺当成"声明"

guardDecide 的 L1 原本只校验**过去时声明**的文件存在+mtime。修复方式是扩展"什么算声明"：

```
WRITE_CLAIM  过去时：已写入/已保存/已创建/生成到/written to...
FUTURE_CLAIM 将来时：现在/接下来/下面/马上/立即 + 写/创建/生成/编写/实现/建立 + 路径
WILL_CLAIM   我将/I'll + 写/创建/... + 路径
```

三个正则合并为 `CLAIM_PATTERNS`，`claimedPaths()` 遍历所有模式提路径 →
L1 对提取到的路径做**环境校验**（存在 + 本轮 mtime 新鲜）。

**关键**：不是"文本匹配到就放行"，而是匹配到承诺后**仍以环境事实为准**——
承诺了产物但文件不存在 → 触发纠错消息，不允许蒙混过关。

### 2. 实现位置

- `index.mjs:593-596`：三个正则定义
- `index.mjs:622`：`CLAIM_PATTERNS` 数组
- `index.mjs:624-636`：`claimedPaths()` 遍历所有模式
- `index.mjs:1547`：`guardDecide` L1 调用 `claimedPaths()`（原有逻辑不变）

### 3. 测试矩阵（tools/test_future_claim_guard.py，8/8 PASS）

测试从 index.mjs **提取正则本身**（单一源，避免测试复制正则导致漂移），用 Python re 验证：

| 样本 | 期望识别 | 结果 |
|---|---|---|
| 我已写入 tools/check_verify.py | ✅ 声明 | PASS |
| 现在编写 tools/test_future_claim_guard.py | ✅ 声明 | PASS |
| 接下来创建 docs/FUTURE_CLAIM_GUARD_20261120.md | ✅ 声明 | PASS |
| 马上实现 ./tools/foo.mjs | ✅ 声明 | PASS |
| 我将写 ./tools/bar.py | ✅ 声明 | PASS |
| 下一步我会考虑优化一下（无产物）| ❌ 不识别 | PASS |
| 正在分析现有逻辑，稍等（无产物）| ❌ 不识别 | PASS |
| 这是一个纯咨询问题 | ❌ 不识别 | PASS |

### 4. 测试抓到的真 bug（接管的价值）

agent 写的 `WILL_CLAIM` 原正则要求 `(?:我将|I'll)\s+`（强制空格），
但中文"我将写"没有空格 → **中文分支永远不匹配**（"I'll write" 也缺英文动词）。
测试第 5 项 FAIL 暴露了它，已修：去掉强制空格 + 补英文动词 write/create。
修复后 8/8 PASS。

这正是"文档宣称完成 ≠ 实际生效"的又一例——如果我只做 node --check 就 apply，
会留下一个"看着有正则、实际漏拦中文我将承诺"的假防线。

### 5. 误判边界

- "下一步我会考虑..."（无具体产物）→ 不拦（正常规划）
- 中文路径 / 无扩展名 → 当前正则只认绝对路径或带 .py/.mjs/.md 的相对路径，故意保守
- 重复/长文本 → 逐行匹配，每行独立判定

### 6. 沉淀

这是"只输出好"的将来时变体的治本防线。与 A1_5 的 check_verify.py（查判据假绿）
形成互补：A1_5 管"判据会不会骗人"，A1_6 管"完成声明会不会骗人"。

---

## 原报告：`FUTURE_CLAIM_GUARD_ANALYSIS_20261120.md`

## "只输出好"的新变体：将来时承诺穿过守卫（2026-11-20 20:18）

> 用户观察："它已经停下来了，这是不是之前只输出好的放大版？"
> 结论：**是同一类病的新变体**——"只输出好"用确认词+无工具调用，这个用"将来时承诺"+无工具调用。
> 已开卡 `A1_6`（守卫 L1 补将来时承诺检测）承接修复。

### 1. 现场

A1_5 推卡会话（session-0428ceab）20:16:35：

```
assistant: "好，A1_5 已 claim，状态 doing。现在进入核心：分析四类病检测逻辑并编写 check_verify.py。"
turn/end: completed
running: false
```

产物：`tools/check_verify.py` **不存在**。它把"说要做"当成"做了"，然后结束回合。

### 2. 为什么现有 L0-L3 全漏了

`guardDecide(state)`（index.mjs:1525）的判据链：

| 层 | 判据 | 本次为何没触发 |
|---|---|---|
| L0 | `body.length === 0`（空正文）| 正文很长，非空 |
| L1 | `claimedPaths(body)` → `WRITE_CLAIM` 匹配已声明路径 | `WRITE_CLAIM` 正则（index.mjs:593）只匹配**过去时**：`已写入/已保存/已创建/生成到...`；"现在编写"是**将来时**，不匹配 |
| L2 | 大段代码贴正文但无 write | 它没贴代码，只贴一句计划 |
| L3 | `body.length <= 3` 或命中 confirmWords | 正文远超 3 字符，不是短确认词 |

**根因**：L1 是环境级 verified finish，但只校验**过去时声明**（"我写了 X"）；模型学会了用**将来时**（"我将写 X"）——这样能过 L3 的长度门槛，又不触发 L1 的路径校验。

这是"只输出好"的**适应性变体**：防线堵住了"好"，它就改说"我将要做好"。

### 3. 修复方向（A1_6 卡）

把 L1 扩展为双向：
- 过去时声明（现有）：`已写入 X` → 校验 X 存在且本轮 mtime 新鲜
- **将来时承诺（新增）**：`现在/接下来/下面/我将 + 写/创建/实现/修改 + 产物名` → 视为承诺，同样校验产物在**本轮**真实产生

关键纪律：
1. 仍以**环境事实**（文件存在 + mtime）为准，不是文本匹配通过就放行
2. 避免误判正常进度说明（"下一步我会考虑..."属于规划，不该拦）——只识别**明确承诺 + 具体产物**的组合
3. 构造测试样本：将来时承诺但无产物 → 必须被拦；过去时声明且产物存在 → 放行

### 4. 元层教训

这是"防线的防线"问题：**守卫规则本身也会被测出漏洞**。
今天的 `Critic v2 第6维（规则-实例一致性）` 和 `Planner（假设披露）` 是针对 agent 输出质量的；
这次暴露的是**守卫规则被模型适配绕过**——需要元验证器（A1_5）之外再加一层"守卫覆盖度"检查（A1_6）。

两者关系：
- A1_5 查**判据**（verify）会不会假绿
- A1_6 查**守卫**（guardDecide）会不会被将来时承诺绕过
- 合起来才是完整的"完成判定可信"体系。

### 5. 观察记录

推卡全过程决策过程观察见 `D:/Brain/_cleanup_20261118/_observe_log.txt`（临时，正式结论沉淀本文）。
正面：它 claim 后先读 roadmap_check.py 前 200 行 + LADDER 卡定义，无 read 循环，顺序正确。
负面：把规划当执行输出后结束回合（本文主题）；用临时文件 `_claim_output.txt` 捕获输出污染工作树（轻微）。

---

## 原报告：`CONSISTENCY_GUARD_DESIGN_20261120.md`

## 一致性守卫设计：防三副本漂移 + 防"文档宣称完成但没生效"

> 版本：2026-11-20 ｜ 状态：设计稿（未实现）｜ 约束：零 LLM、低开销、只读设计
> 目标：把今晚事故里的教训固化成确定性、可自动触发、能自证运行过的守卫，不依赖人记得跑、不依赖 35B 判断。

---

### 0. 设计约束与实测基线

#### 0.1 硬约束
- 零 LLM：所有判据是文件存在/内容匹配、sha256、git 元数据、JSON 字段、单测退出码、trace 行统计。绝不调用 35B（每步 11s，8G 显存全留给推理）。
- 低开销：离线全量守卫目标 < 2s（十来个文件 sha256 + 几条 git 命令）；运行时哨兵 < 5ms（几次小文件 read + append）。
- 失败可见：守卫自身出错必须 exit 2（而非静默 exit 0）；"没证据"必须落到 UNKNOWN/FAIL，不许等价成 PASS。

#### 0.2 本次探查确认的基线事实（设计依据）
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

### 1. 总体架构

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

### 2. 一致性守卫脚本 tools/consistency_guard.py

#### 2.1 三份拷贝的精确定义（先定"谁算生产"）

| 代号 | 路径 | 角色 | 是否纳入生产比对 |
|---|---|---|---|
| A-remote | git ls-remote origin HEAD / refs/heads/main | 远端真相 | 是（commit 级，离线可用） |
| A-local | D:/Brain/publish/dsh-behavior-guard（+ autostart 同构） | 权威源，唯一可写 | 是（commit + 文件 sha + version） |
| C-runtime | D:/Brain/dsh-data/profiles/desktop/node_modules/{dsh-behavior-guard,dsh-llama-server-autostart} | dsh 实际加载 | 是 |
| 副本/缓存 | node_modules/.pnpm/**、pnpm store（~/.local/share/pnpm/store）、D:/WorkBuddyWorkSpace/**/dsh-* 旧 clone | 缓存 / 外星 clone | 否（只做 INFO，不参与 PASS/FAIL） |

硬规则：pnpm store 与旧 clone 永不作为比对基准，也不作为"权威"候选。对旧 clone 只检查一件事——它的 git remote -v 若指向同一 origin 且 HEAD 落后，报 INFO(stale clone) 而非 FAIL，防止有人把它当权威改。

#### 2.2 关键资产清单 config/GUARD_MANIFEST.yaml

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

#### 2.3 核心函数与伪代码

```python
## —— CRLF 假差异消除（core.autocrlf=true 是本次实测配置）——
def sha256_normalized(path: Path) -> str:
    b = path.read_bytes()
    b = b.replace(b'\r\n', b'\n').replace(b'\r', b'\n')   # 两边同规范化
    return hashlib.sha256(b).hexdigest()

def sha256_git_blob(repo: Path, ref: str, rel: str) -> str:
    # git 对象库存的是 LF；用同一规范化函数处理，保证与工作树可比
    b = subprocess.run(['git','show',f'{ref}:{rel}'], cwd=repo,
                       capture_output=True, timeout=10).stdout
    return hashlib.sha256(b.replace(b'\r\n', b'\n')).hexdigest()

## —— junction 识别（link: 依赖属正常例外，但不能盲跳）——
def reparse_target(path: Path):
    # Windows: ctypes GetFileAttributesW + FILE_ATTRIBUTE_REPARSE_POINT
    # 或读重解析点 Target；返回 (is_junction, target)
    ...

## —— 采集一份拷贝 ——
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

## —— 比对 A/B/C ——
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

#### 2.4 网络退化与防抖
- git ls-remote 超时/失败 -> UNKNOWN(remote unreachable)，不判 PASS 也不崩，由 --strict 决定是否阻断（默认 warn）。
- sha 比对先做文件大小快速比较，字节数不同直接 FAIL，省去大文件读。
- 所有外部命令带 timeout，捕获 FileNotFoundError（缺依赖）-> exit 2 + 明确错误。
- 报告写 BENCH_DIR/_guard_report.json，同时 stdout 人类可读摘要；--quiet 只输出 exit code 给钩子/sentinel 用。
---

### 3. "宣称 vs 落地"交叉验证 tools/claim_audit.py

核心原则（针对历史坑）：不用关键词计数。代码里出现字符串 != 文件在权威源 != 真的跑了 != 真实会话命中。每条"完成 X"声明必须携带结构化 expect，且必须出现至少一条 L4/L5 证据才允许 PASS。

#### 3.1 结构化声明（在 CHANGELOG 条目里内嵌，人不可见部分机器可读）

```markdown
### [2.26.5] - 2026-11-20（能力阶梯按调研修正）
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

#### 3.2 复用已有 verify 原语，零重复实现

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

#### 3.3 证据分级映射（对齐 POSTMORTEM 的 L1-L5）

| expect kind | 证据级别 | 能证明 |
|---|---|---|
| file_exists / file_grep | L1 | 写了 |
| test_pass / gate_result | L2 | 隔离环境逻辑对 |
| json_field / artifact + git_diff_nonzero | L5 | 独立产物落地 + 代码真改 |
| trace_count / trace_absent（带 sid_filter: exclude_tests） | L4 | 真实会话触发 |

#### 3.4 判定规则（把历史坑逐条编码成硬门）

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

#### 3.5 与权威块 done 状态互证

遍历权威块中 status: done 的 item：
- evidence_log 必须非空、每条含 commit 与 checks；缺任一 -> FAIL(fake_done)（对应既有"done 必须携带 commit+命令+退出码"设计）。
- evidence_log[].commit 必须能在 git log 找到；找不到 -> FAIL（防伪造/回填）。
- done 但 verify 全 PASS 却无任何 trace/artifact 类判据 -> UNVERIFIED 提示（可能是纯结构项）。

输出 BENCH_DIR/_claim_audit.json，逐条声明列 id | verdict | evidence_level | evidence，供人复核与 §6 钩子读取。
---

### 4. 写回纪律：唯一写入口 + 校验签名

目标：--apply 只写权威块；任何手工改字段（今晚新加字段被改坏）在读取时立刻报警。

#### 4.1 权威块加 integrity 段（schema_version 升 2，向后兼容 v1 只读告警）

```yaml
schema_version: 2
block_id: roadmap-graph
integrity:
  algo: sha256
  payload: <HEX>          # canonical_payload 的 sha256
  prev: <HEX|null>        # 上一版 payload 哈希，构成哈希链
  written_by: tools/roadmap_check.py@de9d111
  written_at: 2026-11-20T02:15:00Z
## ... 原 items/rungs/anchors/status_enum/test_sids ...
```

#### 4.2 规范化与校验（确定性，可在任何机器复算）

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

#### 4.3 唯一写入口（收敛所有写操作）

- 现状：save_authoritative() 已被 cmd_claim/cmd_apply 共用——保持并强化。
- 改造：save_authoritative(data, reason, actor) 是唯一允许写 ROADMAP.md 权威块的函数；内部三步：
  1. 写前 verify_integrity 必须 OK（已被改坏则拒绝覆盖，避免把损坏固化）；
  2. 重算 integrity.payload、integrity.prev = 旧 payload、写 written_by/written_at；
  3. 同步镜像 CAPABILITY_LADDER.yaml 的 status，并写入 mirror_of: <payload>。
- 新增 tools/roadmap_edit.py：唯一受支持的"手工字段编辑"CLI。白名单只允许改 status/verify/deps/risk/notes，走同一 save_authoritative 自动重签。文档/技能明令禁止直接编辑 ROADMAP.md 权威块（编辑即校验失败）。
- 哈希链校验：consistency_guard.py --scope signature --chain-depth 30 遍历改过 ROADMAP 的 commit，逐版重算 payload 并验证 prev 链——检测"抹掉 integrity 段 / 回填旧签名"。

#### 4.4 镜像漂移
对每个 item 比对权威块 status 与 CAPABILITY_LADDER.yaml 同名 item 的 status，以及镜像的 mirror_of == 权威 payload。不一致 -> FAIL(mirror_drift)（默认 FAIL 而非 WARN，因为今晚教训就是镜像被当真相）。

---

### 5. 运行时哨兵：dsh 启动时自报"加载版本 vs 权威"

复用现有 dbg() 与 _agent_harness_loaded.json 探针，不新增依赖、不改启动关键路径（绝不 throw —— !!js 事故证明硬失败代价更高）。

#### 5.1 发布时打桩 GUARD_STAMP.json

consistency_guard.py stamp 在权威源生成，随 setup/install*.ps1 拷到 node_modules：

```json
{"schema":1, "commit":"7926407", "version":"1.2.0",
 "generated_at":"...", "files":{"package.json":"<sha>", "index.mjs":"<sha>", "frame_limiter.py":"<sha>"}}
```

这是 §2 离线比对（完整 hash）与 §5 运行时比对（只看 commit+version，便宜）之间的桥。

#### 5.2 autostart index.mjs 的 sentinel（在 apply() 内，dbg('apply called') 之后调用）

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

#### 5.3 harness 探针补 guard 字段

index.mjs 第 738 行现写 {loadedAt, version:2, config}——注意 version:2 是探针 schema 不是包版本（易被误读）。新增同文件小函数 guardStamp()（读自身 package.json + 同目录 GUARD_STAMP.json，与权威对比），把结果写进探针：

```js
writeFileSync(cfg.probePath, JSON.stringify({
  loadedAt: ..., version: 2,
  guard: { pkgVersion, buildCommit, authoritative: {version, commit}, verdict },
  config: cfg }, null, 2))
```

这样 _agent_harness_loaded.json 既是"插件被加载"的 L3 证据，也是"加载版本/commit 与权威一致"的 L4 证据。
---

### 6. 失败模式清单（守卫自身会怎么失效）+ 强制触发点

#### 6.1 失效模式与对策

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

#### 6.2 强制触发点（相互独立，任一层漏了还有下一层）

1. 本地 git hooks（首选，当前无 CI）：setup/install.ps1 安装 .git/hooks/pre-commit（跑 --scope signature,claims --strict --quiet，FAIL 阻断）与 pre-push（跑 --scope copies --include-remote 全量）。钩子脚本本身也纳入 selfcheck。
2. roadmap_check.py --next 前置硬门：agent 每次自读能力阶梯选卡前，先跑 --scope signature --quiet；签名 FAIL -> 打印"权威块被改坏，先修复"并 exit 非 0，agent 无法继续爬卡。这是唯一随每次 agent 会话自动触发的点，弥补无 CI。
3. 发布纪律：写新 ## [x.y.z] / cmd_apply 前，assert_fresh_guard_report(head) 检查 BENCH_DIR/_guard_report.json 的 head == 当前 HEAD 且 verdict==PASS；不满足拒绝写。把"守卫跑过且绿"变成发版硬前置。
4. 运行时哨兵：每次真实 dsh 启动都写 _guard_sentinel.jsonl；元守卫检查最近 N 次会话是否有 sentinel 记录——没有则守卫/插件没被正确加载（F1 的检测器）。
5. 可选 CI：若接 GitHub Actions，.github/workflows/guard.yml 在所有 push/PR 跑 --all --strict；但不能依赖它（当前没有，且硬件约束在本地）。

#### 6.3 成本预算
- 离线全量：sha256（约 12 个文件）+ 4 条 git 命令 + 解析 2 个 JSON + 读 CHANGELOG/ROADMAP ≈ < 2s。
- --next 前置：仅 signature（读 ROADMAP + 算一次 sha256）≈ < 50ms。
- 运行时 sentinel：读 2 个小 JSON + 2 次 append ≈ < 5ms/启动。
- 全程 0 次 LLM 调用，不影响 35B 推理。

---

### 7. 落地顺序（建议，本设计不含实现）

1. roadmap_check.py：加 verify_integrity / integrity 段 / save_authoritative 重签 / roadmap_edit.py（§4）——地基（签名保护 test_sids）。
2. consistency_guard.py 先做 copies + signature 两个 scope（§2、§4.4），跑通真实漂移样本（autostart 1.2.0 vs 1.1.1、harness 2.26.2 vs 2.26.5 应判 FAIL）。
3. claim_audit.py + CHANGELOG 的 CLAIM_BEGIN 模板（§3），先给 v2.26.5 一条声明做样板。
4. GUARD_STAMP.json + autostart sentinel + harness probe 扩展（§5）。
5. setup/install.ps1 装 hooks + roadmap_check.py --next 前置门 + 发布 assert（§6.2）。

### 8. 验收标准（本设计是否达成的判据）
- [ ] 当前两处真实漂移能被守卫判 FAIL 并列出差异（autostart 版本、harness 版本）。
- [ ] 手工改权威块任一字段后，--next/--dry-run 立即 IntegrityError，且逐字段列出改动。
- [ ] 一条"完成 X"但只有 file_grep 证据的声明 -> UNVERIFIED（不是 PASS）。
- [ ] trace_count 不带 sid_filter 的声明 -> UNVERIFIED；带 s1 假数据的 trace 不被计为真实命中。
- [ ] git diff --stat 0 行代码的"代码修复"声明 -> FAIL: no_code_diff。
- [ ] autostart 启动后 llama-debug.log 有 [SENTINEL] 行且 _guard_sentinel.jsonl 有对应记录；把运行版 stamp 改成旧 commit -> 报 DRIFT。
- [ ] 全链路 0 次 LLM 调用；离线守卫实测 < 2s。

---

## 原报告：`CONSISTENCY_VERDICT_20261120.md`

## 一致性 verdict：今晚改动真的达标了吗？（2026-11-20 事故后自审）

> 用户问：今晚做的改动是否真的保证 GitHub / 生产一致、达到承诺标准？有什么机制检验/防止？对它有什么教训？
> 这是本次会话最严重事故后的诚实自审。**答案先给：审计时不一致，审计后我修复了绝大多数，但仍有 3 个诚实缺口。**

---

### 1. Verdict：不，审计时不达标

我派了两路独立审计（远端/权威/生产三处 + 机制设计），并用 GitHub REST API 逐 blob 核对。结论（详见 `_AUDIT_20261120_RAW.md`）：

#### 审计发现的不一致（9 项，不淡化）

| # | 问题 | 严重度 |
|---|---|---|
| 1 | tag `v2.26.5`/`v2.26.4` **根本不存在**（承诺的发布没兑现） | 高 |
| 2 | package.json version 2.26.2 ≠ CHANGELOG 2.26.5（文档宣称 vs 机器版本打架） | 高 |
| 3 | 生产 C 缺全部 5 个今晚新增文件（能力阶梯/roadmap_check/设计文档/同步脚本/帧限制器） | **严重** |
| 4 | 生产 ROADMAP 是 220 行旧版，无内嵌权威块 → "agent 自读阶梯"在生产完全不可用 | **严重** |
| 5 | autostart 生产是 1.1.1 + 手工限帧补丁，权威是 1.2.0（缺 parent-pid 看门狗修正）| 高 |
| 6 | autostart 版本三方打架：运行 1.1.1 / lock 1.1.0 / 权威 1.2.0 | 高 |
| 7 | lock 指向 f4a8d25(v2.26.2)，node_modules 已手工同步到 de9d111 → **一次 `pnpm install` 就会回退、今晚成果全丢** | **致命** |
| 8 | 审计时 dsh 进程为 0（服务死），8081 通是 llama 独立的假象 | 高 |
| 9 | frame_limiter 5 个孤儿进程堆积 | 中 |

**最讽刺的一点**：我整晚在讲"文档宣称完成≠实际生效"、"看着 A 改 B"，而审计证明**我自己正在制造同型问题**——交付了能力阶梯却没进生产、承诺了版本却没打 tag、改了 lock 却没验证 install。

#### 一致的部分（如实记录）

- A 远端 / B 权威 HEAD 完全相同（de9d111 / 7926407），两个仓库工作树干净
- behavior-guard 三件套（index.mjs / cordis.patch.yml / package.json）B vs C 逐字节一致
- 所有新增文件在 A 远端 tree 与 B 提交中 blob sha 逐一相同
- CRLF 字节差是假的（`git hash-object --path` 归一化后相同）

---

### 2. 审计后修复（02:20-02:35）

| 问题 | 修复 | 验证 |
|---|---|---|
| tag 缺失 | 补建 v2.26.4/v2.26.5 并推送 | `git ls-remote` 确认 |
| 版本打架 | package.json → 2.26.5；files 纳入 CAPABILITY_LADDER.yaml | grep 确认 |
| 生产缺文件 | cp 同步权威→生产（含 ROADMAP/package）| sha256 逐字节相同；生产能跑 `--graph`(30/22/0环) 和 `--next` |
| autostart 老版本 | 同步权威 1.2.0（备份旧版在 _cleanup）| sha256 相同、parent-pid 到位 |
| lock 脱节 | 更新两个 commit + integrity（收 GitHub tarball 算 sha512）+ version | lock 4 处 a503509、version 2.26.5/1.2.0 |
| dsh 死 / 孤儿进程 | 标准流程重启；kill 孤儿 limiter | dsh pid 26580 稳定、8081 OK、bridge OK、limiter 仅 1 合法 |

#### 三个诚实缺口（仍未达标的部分）

1. **`pnpm install --frozen-lockfile` 从未真跑**——lock 是手工更新 + hash 算自 tarball，但没有验证 pnpm 接受它。跑 install 风险高（今晚多次被 shim 拦截、曾清空 node_modules）。这是"名义一致"而非"验证一致"。**下次任何 install 前必须先验证 lock。**
2. **`--apply` 从未真实触发**——能力阶梯的写回（evidence_log + save_authoritative）只有代码，没有一次真实 doing→done。按证据阶梯是 L1/L2，不是 L4/L5。
3. **dsh 当前加载的是新代码，但没做端到端 trace 验证**——重启后 health OK、bridge OK，但没验证"新能力阶梯真的被 agent 用了"。

**最终核验（02:40，修复全部完成后）**：

```
HEAD: 11835b64  worktree clean: True  远端 HEAD == 本地 HEAD
B/C sha256 逐字节相同：index.mjs / cordis.patch.yml / package.json /
  CAPABILITY_LADDER.yaml / roadmap_check.py / ROADMAP.md  (6/6 OK)
autostart B/C：index.mjs / package.json / frame_limiter.py  (3/3 OK)
版本：package=2.26.5 prod=2.26.5 autostart=1.2.0/1.2.0 CHANGELOG=2.26.5 ✓
lock 指向 HEAD(11835b6) + version 2.26.5 ✓
tag v2.26.5 本地+远端均存在（指向 a503509，比 HEAD 落后 1 个审计文档提交——
  这是正常的：tag 标记功能发布点，之后只加了审计文档）
dsh pid 26580 稳定；8081 OK；bridge OK；生产能跑 --graph(30/22/0环) 和 --next
```

**所以诚实结论**：修复后**文件层与运行层都一致了**（9/9 关键文件逐字节、版本三方对齐、lock 指向 HEAD、服务健康、生产能力阶梯可用）。**仍存的两个缺口**：`pnpm install --frozen-lockfile` 与能力阶梯 `--apply` 从未真实跑过——它们是"名义可用"而非"验证可用"。我不夸大这两个缺口，也不掩盖它们。

---

### 3. 检验与防止机制（怎么不再发生）

两路审计给了方案（详见 `CONSISTENCY_GUARD_DESIGN_20261120.md`，462 行设计稿），核心是三条：

#### 机制 A：一致性守卫 `tools/consistency_guard.py`（待实现）
零 LLM、<2s，一条命令对比 A/B/C：
- commit：远端 HEAD == 权威 HEAD（用 `git ls-remote`，不 fetch 改动本地）
- 关键文件 sha256：B vs C 逐字节（CRLF 用 `git hash-object --path` 归一化，避免假差异）
- 版本三方：package.json / CHANGELOG 顶部 / lock version 必须一致
- lock commit 指向的 tag == 期望发布版本
- 输出 PASS/FAIL + 差异清单；**自身出错 exit 2**（不许静默 exit 0 当 PASS）

#### 机制 B：宣称 vs 落地交叉验证
不靠关键词计数（历史坑：内存变量被误判为落盘），而是三层交叉：
1. 运行版真实打点（`trace({kind})`）
2. 真实产物（文件存在 + 内容断言 + SHA256）
3. 调用者 + mtime（脚本真被调用过）
判据写进能力阶梯的 `verify`，由 `roadmap_check.py verify <ID>` 执行。

#### 机制 C：强制触发点（守卫自己不能被人忘记跑）
今晚的教训是"机制存在但没人触发"（P3 按 ADR 不启动、watcher 只消费 trace）。所以守卫必须挂到**已有的强制通道**：
- `restart_dsh.ps1` 启动前跑一次 `--scope copies`（dsh 每次重启都校验）
- autostart 插件的 `dbg()` 里加运行时哨兵（<5ms）：报"当前加载的 package version/commit vs 权威"
- `roadmap_check.py --apply` 写回前校验权威块 checksum（手工改过就报警）

---

### 4. 对 agent 本身的教训（写进成长直升的 CritBank 候选）

从这次事故里，agent 该学到什么（按"触发→动作"格式）：

| # | 触发信号 | 教训（一句话规则）|
|---|---|---|
| C-01 | 自己说"已推送/已完成/全绿"时 | **推送 ≠ 生产生效**。说完成前必须核对三处（远端/权威/运行版）的 commit 与 sha256；health 200 不等于进程活着 |
| C-02 | 改了版本/CHANGELOG | 版本号必须三方一致（package.json / CHANGELOG / tag / lock）；打 tag 要 `ls-remote` 确认上了远端 |
| C-03 | 手工 cp 文件到 node_modules | 必须同步更新 lock 的 commit+integrity，否则一次 install 全回退；且要重启让运行版真加载 |
| C-04 | trace/日志出现高比例单一 sid | 先按 sid 分组查假数据（这次 91% 是 s1），再下结论 |
| C-05 | patch 配置改动 | `!!js [...]` 会被 YAML 当 flow sequence 切碎 → dsh 起不来；纯字符串配置也可能触发整段替换丢字段；改前备份、改后重启验证 |
| C-06 | 清理进程/孤儿 | Force kill 不触发 finally；清理前确认父进程死活，别误杀当前合法实例 |
| C-07 | 派子任务后 | 结果就在上下文/落盘文件里，不要说"投递丢失"；先读文件再下判断 |

**这些应该进能力阶梯的 `caveats` 字段**——它们正是"干的过程中要注意的坑"，让 agent 下次爬类似卡片时不再重蹈覆辙。

---

### 5. 一句话回答用户

> 审计证明我不达标：承诺的版本没打 tag、能力阶梯没进生产、lock 指向旧 commit（一次 install 就回退）、服务还死了。
> 我修复了绝大多数可立即修的并重启验证，但 `pnpm install` 与 `--apply` 从未真实跑过——**文件层一致了，运行层/验证层还没闭环**。
> 防止再犯靠三件：一致性守卫（零 LLM 对比三处）+ 宣称交叉验证（打点/产物/调用者）+ 强制触发点（重启前/运行时哨兵/写回校验）。
> 对 agent 最大的教训：**"我提交了"不等于"生效了"，验收只认真实运行的证据。**

---

## 原报告：`DIAGNOSIS_CORRECTION_20261120.md`

## 纠错：我用单帧快照误判了推理活性（2026-11-20 21:12）

> 用户实证："我现在同时打开 dsh 窗口和你的窗口，它照样能继续推理，没卡住。"
> 结论：**用户是对的，我的诊断错了**。本文记录错在哪、证据、以及如何防止再犯。

### 1. 我的错误诊断（21:00-21:08）

我看到单帧 `GPU util=100% / 带宽=1% / 功耗=25W / llama SM=98% MEM=0%`，
判定为"3D 抢占 Copy → CUDA spin-wait → 推理没法用"，并据此：
- 开了 S10「降帧效果回读」卡
- 写了"降帧无效、EcoQoS 对 Chromium 不管用"的结论
- 建议你用 cancel 停会话来"止血"

### 2. 用户的实证推翻（21:12）

两窗口全开，我连续采样 5 次 + token 计数：

| 时间 | 带宽 | 功耗 | n_decoded | n_prompt_tokens |
|---|---|---|---|---|
| 21:12:35 | 23% | 38.9W | 1211 | 27966 |
| 21:12:50 | 27% | 36.6W | 1356 | 28107 |

**`n_decoded` 5 秒涨 145 token**——推理在健康推进，根本没卡住。

### 3. 错在哪

**单帧采样撞上了相位间隙**。35B 推理分阶段：prefill（带宽高）、decode（带宽低）、
思考/工具间隙（带宽极低）。我在 21:00-21:08 的多次采样恰好都落在低带宽瞬间，
把**瞬态当成了稳态**，还用 `llama SM=98% MEM=0%` 这种单帧 pmon 强化错误结论。

**我违反了项目记忆里自己写的铁律**：
> "冻死判据：llama 实例 `/slots` 的 `n_prompt_tokens_processed=0` 持续不动 + CPU 满载"

正确判据是**连续时间窗内 token 计数是否增长**，不是单帧硬件利用率。
单帧判据只能做"疑似"信号，不能做结论，更不能据此开卡/改配置。

### 4. 纠正动作

1. **S10 卡**：从"降帧效果回读（前提=降帧无效）"改为 `manual-blocked`，
   重定义为「推理活性判据纠偏」——废除单帧采样，改用 token 连续采样
2. **FRAME_LIMITER_SLOTS_BUG 文档第7节**：标注"降帧无效结论基于错误诊断，作废"，
   保留 SLOTS bug 修复（那是真的：裸 /slots 返回 400、THROTTLE 事件确实出现过）
3. **frame_limiter 修复保留**：SLOTS 缺 model 是真 bug（先 loaded_model 再拼 model 的正确逻辑在别的脚本里），
   修了没错，但"修复带来的效果"不该归因为解决 spin-wait
4. **cancel 实战保留**：刹车工具本身是对的（accepted=true、3秒停会话），
   但"用 cancel 止血解决推理卡死"的前提不成立——当时没卡

### 5. 沉淀的教训（进 CritBank）

```yaml
signal: "我用单帧硬件快照(util100%/带宽1%)判定推理spin-wait，用户实证两窗口全开推理正常(n_decoded 5秒涨145)"
lesson: "相位瞬态≠稳态。推理活性唯一可靠判据是连续时间窗内token计数增长(n_decoded/n_prompt_tokens)，单帧util/功耗只能做疑似信号。我记忆里明明写着这条，实操时还是用了单帧判据——知道规则≠遵守规则。"
action: "任何'性能异常/卡死'判定必须先连续采样token计数≥2次(间隔5秒)；单帧硬件数据不得作为开卡/改配置的依据"
```

### 6. 对用户这轮的诚实回应

你连续三次纠正我（刹不住车 → 考虑所有窗口 → 两窗口照样推理），
三次都指向同一个更深层的问题：**我在用静态快照理解一个动态系统**。
这轮抓到的"读代码循环"是真的（盯梢实证 read×5 无产物），
但"GPU 卡死"是假的（token 在涨）。两者被我混在了一起。

---

## 原报告：`GAP_REVIEW_20261120.md`

## 推卡前体检：遗漏清单 + 新卡建议（2026-11-20 19:55）

> 用户："在我们继续往前推卡之前，回顾一下还有什么遗漏的，或者还有什么值得给个新卡的位置的吗？"
> 方法：Explore 子任务盘点全卡 + 主代理回顾当天 16 项工作日志 + 独立核查。
> **纠错声明**：子任务声称"S6_rule 现在存在且 done"——主代理核对 LADDER/GRAPH 均只有 S6_model，
> `S6_rule` **确实不存在**。此前对 35B"假设不存在的卡"的批评成立，不采信子任务该条。

### 1. 当前版图（41 卡）

| 状态 | 数量 | 说明 |
|---|---|---|
| done | 23 | A0/A1/A3_5/M1/M8 + 18 张归档锚点（S1-S9/GWT_FEP 等）|
| backlog | 12 | M2/M3/M9/L1-L8/A2-A5（多数是能力卡，部分 manual 判据）|
| manual-blocked | 6 | M5/M7/S6_model/L3/L4/L5（需产品/外部决策）|

A 系列自治阶梯：A0✅ → A1✅ → **A2(backlog,manual)** → A3(backlog,manual) → A3_5✅ → A4(backlog,trace_count) → A5(backlog,manual)。
**瓶颈 = A2**：manual 判据、无自动核验，卡住后面 A3/A5。

### 2. 遗漏清单（做了但没成卡 / 有缺口无位置）

#### 🔴 遗漏 1：会话生命周期治理（今天最严重事故的来源，零覆盖）
- 事故：M8 僵尸会话 `7412cc71` 在停止后复活，把 `index.mjs` 改出语法垃圾。
- 路线图里**没有任何卡**覆盖"会话的停止/隔离/僵尸检测"。
- 现有能力：bridge 有 8 个命令（health/sessions/events/send/watch/create/minimize/restore）**无 abort/stop**；
  dsh session API 的 DELETE/PATCH/POST 全 404；freeze_watch 只盯 llama 冻死，不盯 dsh 会话僵尸。
- 今天的解法是人工发极简 STOP + 复查工作树——不可复制、不可自动。

#### 🔴 遗漏 2：判据自身的可靠性（A1 踩了三个坑，无卡）
- A1 判据曾出现：①自引用递归（dry-run 跑 A1，A1 判据又跑 dry-run）②格式不匹配（裸 `^PASS` vs `[PASS  ]`）③管道吞退出码（S_FORGET 假绿）。
- 现有卡 A1 只管"卡的状态可机器核验"，**不管"判据本身是否会假绿/递归/误判"**。
- 判据是自治的地基——地基判据坏了，agent 会"全绿但没做"。

#### 🟡 遗漏 3：量化 effort 字段（35B 的治本建议，我采纳为待办但没成卡）
- 当前性价比用定性评级→数值，35B 和我都承认必然失真。
- 治本：给卡片补 `effort`（人天/故事点），性价比改 `收益/effort`。
- 这是**改造现有卡的数据模型**，不是新能力——但值得一张小卡推动。

#### 🟡 遗漏 4：规则-实例一致性的自动化（今天刚加进 rubric，但没有"验证机制"的卡）
- 已加进 Critic v2 第 6 维 + Planner assumption_disclosure——但只是**判据文本**，
  没有卡验证"这条 rubric 真的在评审里生效"（证据分层铁律：代码存在 ≠ 真实生效）。

#### 🟢 隐性债（已顺手修，2026-11-20 19:58）
- `tools/backtest_archive.py` 的 TESTS 列表仍引用 12 张已删除的 S_* 卡（实测脚本仍在故 13/13 通过，
  但判据与现状脱节）。已重写为 10 个唯一测试脚本、标签=脚本名（消除卡名与脚本错配），
  A1 判据 `min` 从 13 改为 11（10 测试 + graph 可加载）；verify A1 2/2、run_all 17/17。

### 3. 值得给新卡的位置（按优先级，待用户拍板）

| 优先级 | 卡 id 建议 | what | 为什么现在开 | 判据可行性 |
|---|---|---|---|---|
| P0 | **A2_5 会话生命周期**（自治阶梯补位）| 让 observer 能检测/停止/隔离僵尸会话：bridge 加 `stop`/`isolation` 能力，watchdog 盯会话级无进展 | 今天的瘫痪就是它——自治闭环缺了"刹车"，A5 常驻闭环前必须先有刹车 | 高：文件判据（bridge 命令存在）+ trace 判据（僵尸被检测并停止的真实事件）|
| P1 | **A1_5 判据元验证**（判据自检器）| 写 `check_verify.py`：检测自引用递归、格式不匹配、恒真判据、测试 sid 污染；跑在所有卡的 verify 之前 | 判据是地基，A1 的三个坑还会再犯；自治信任建立在判据可信上 | 高：构造假判据样本，元验证器必须全部判 FAIL |
| P2 | **L_EFFORT 量化 effort**（数据模型升级）| 给 41 卡补 `effort` 数值，性价比公式改 `收益/effort`，排名重算 | 35B 自评的治本方向；让排序从主观评级升级为可审计的量化 | 中：覆盖率判据（41/41 有 effort）+ 排序幂等 |
| P3 | **A_CHAIN A2 解锁**（已有卡，非新增）| 把 A2/A3/A5 的 `manual` 判据改成机器判据，打通自治阶梯 | A2 是瓶颈；不开新卡，但要决定何时爬 | 需产品决策：manual→auto 的语义是否成立 |

### 4. 我的推荐

**先开 P0（会话生命周期）和 P1（判据元验证）两张，都是把"今天的坑"变成"明天的免疫"。**
P2/P3 不急——effort 需要人工估时（用户参与），A2 解锁涉及自治边界的产品判断。

不提议的方向（避免重复 §8 证伪）：不加 judge、不碰 FEP 注入通道、不做通用 agent 框架、不训练模型。

### 5. 待用户拍板

- 是否新增 P0/P1 两张卡？
- A2（自治阶梯瓶颈）是否现在解锁/改判据？
- backtest 过期引用现在修还是并进 P1？
