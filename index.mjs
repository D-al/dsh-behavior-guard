/**
 * dsh-behavior-guard（v3.3 audit-loop + turn-continuation-guard 合并版）
 * 原名 dsh-audit-loop v2 —— 监控-修正闭环 + 纠正角色实时化（2604.11465 完整三角色）
 *
 * v1（2026-11-17 上午）：每 N 步无历史审计 → ISSUE 则注入一句话 fix 指令。
 * v2（本次升级）：审计发现 ISSUE 后，**独立纠正器**（第二次无历史调用）依据
 *   环境事实证据（glob/ls 等成功结果全文）产出结构化修正包——直接算出正确参数，
 *   而不是让主模型自己执行建议。主模型从"执行建议"降为"抄答案"。
 *
 * 依据：
 *  - 2604.11465：纠正器无法访问对话历史 → 打破重复失败循环；
 *    8B 脚手架后超过 33B。实测（2026-11-17）：昨天漂移会话 7 次重试时，
 *    正确答案一直在 step3 的 glob 成功结果里——把证据喂给无历史的纠正器即可定位。
 *  - GUARD（ACL 2026）：失败后顺着第一个念头走是认知螺旋；
 *    纠正器注入的修正包替代"第一个念头"。
 *
 * 降级链：纠正器失败/JSON 解析失败 → 退回 v1 的一句话 fix 注入。
 * 安全阀：fetch 失败静默；每轮 <=1 次注入、每会话 <=4 次；注入后清轨迹防重复。
 */

import { randomUUID } from 'node:crypto'
import { writeFileSync, readFileSync, readdirSync, statSync, existsSync, appendFileSync, openSync, readSync, closeSync } from 'node:fs'
import path from 'node:path'
import { execFile, execFileSync } from 'node:child_process'

export const name = 'agent-harness'

const DEFAULTS = {
  enabled: true,
  auditEverySteps: 8,
  // D5 审计门控（SAG gated critique，2026-11-17）：不再按固定步数审计，改风险信号触发
  // （连续失败≥2 / 无进展≥noProgressSteps / present 前 / 压缩后）。
  // 依据：SAG（SKKU/Soongsil 2026-10）算力 -66% / 成功率 3 倍；"precision intervention
  // > constant supervision"。确定性信号 D1/D2/D3 仍每步零成本检查。
  noProgressSteps: 6,
  endpoint: 'http://127.0.0.1:8081/v1/chat/completions',
  model: 'Qwen3.6-35B-A3B-UD-Q4_K_XL',
  auditTimeoutMs: 90000,
  correctorTimeoutMs: 90000,
  // 证据类工具：成功结果全文保留（截断到 evidenceMaxChars）
  evidenceTools: ['glob', 'grep', 'pwsh', 'list_agents', 'job_output'],
  evidenceMaxChars: 2000,
  // v3 代执行器：只读操作由插件确定性执行（构造性消除传递损耗）
  executorEnabled: true,
  workspaceRoot: 'C:/Users/Ad/Documents/deepseek-harness/default-workspace',
  // 路径安全边界：绝对路径必须落在这些根内才允许代读
  allowedRoots: [
    'C:/Users/Ad/Documents/deepseek-harness/default-workspace',
    'D:/WorkBuddyWorkSpace/2026-10-13-20-41-43',
    'C:/Users/Ad/.dsh',
    'C:/Users/Ad/.workbuddy',
    'D:/llama.cpp',
    'D:/GGUF_Download'
  ],
  executorMaxChars: 4000,
  maxInjectionsPerTurn: 1,
  maxInjectionsPerSession: 4,
  // v3.2 自适应窗口：轨迹出现异常（FAIL/UNPRODUCTIVE）后审计加密到此间隔
  auditEveryStepsAnomaly: 4,
  // v3.2 代验收：spawn_teammate 验收 wait 连续超时 → 插件直接跑 verify_agent.py（三态环境判定）
  verifyEnabled: true,
  verifyScript: 'D:/WorkBuddyWorkSpace/2026-10-13-20-41-43/bench/verify_agent.py',
  pythonPath: 'D:/Python/python.exe',
  verifyTimeoutMs: 120000,
  verifyMinWaits: 2,
  // 共享每轮注入预算（audit 注入 + D4 steer 合计，防叠加刷屏）
  sharedMaxPerTurn: 3,
  // D4 present-gate（verify-gated completion）：present 声明交付时，本轮若无独立验收痕迹
  // （spawn 验收者 / 跑过 verify_agent.py）→ turn-stopping steer"做的人不能自己签字"。
  // 依据：IOV Labs 896 任务实测——小模型虚假完成 ~13%，自检仅降 0.9 个百分点（同一盲区）；
  //       verify-gate / done gate 社区实践：完成判定必须由独立方或环境给出。
  presentGateEnabled: true,
  maxPresentGatePerTurn: 1,
  maxPresentGatePerSession: 2,
  probePath: 'D:/Brain/workspace/bench/_agent_harness_loaded.json',
  // CritBank：结构化失效教训库（零 LLM 成本的检索式注入；U-Fold 检索式上下文思路）
  critbankPath: 'D:/Brain/workspace/bench/critbank.json',
  // ── 任务连续性（2026-11-18 合并自 dsh-task-continuity）──
  // P0 压缩存档（MemGPT/Hippo/ARC）+ P1.5 todo 回灌（Manus recitation）+ P1 todo 闹钟（2609.38108）
  continuityEnabled: true,
  archiveHeader: '[harness 任务存档] 本会话经历压缩。以下是自动维护的任务状态，以此为准：',
  noTodoStepThreshold: 4,
  staleStepThreshold: 5,
  maxTodoInjectionsPerTurn: 1,
  maxTodoInjectionsPerSession: 4,
  todoEchoEnabled: true,
  maxEchoItems: 12,
  ledgerPath: 'D:/Brain/workspace/bench/_compaction_ledger.jsonl',
  messageNoTodo: '[harness 执行检查] 这是一个多步任务，但你还没有用 todo_write 建立任务清单。立即停下：先调用 todo_write 写出完整步骤清单（每条 = 动词 + 目标 + 完成标准，末尾加 [VERIFY] 验证项），把第一项标为 in_progress，然后按清单顺序执行。',
  messageStale: '[harness 执行检查] 你已经连续多步没有更新 todo 清单了。立即回到清单：把刚完成的项标为 completed，把下一项标为 in_progress，再继续执行。如果发现实际工作与清单偏离，先修订清单再继续。',
  // 审计员自校准：每次干预记录到 jsonl，3 步后结算"注入后是否还有新失败"（有效/无效）
  auditFeedbackPath: 'D:/Brain/workspace/bench/_audit_feedback.jsonl',
  // ── MTP 信心信号（2026-11-17，SU/SAG 的零改动代理）──
  // llama-server 每次请求都会打印 "draft acceptance = 0.89 (X accepted / Y generated)"——
  // 这是 MTP draft 头与主模型的一致率：低接受率 = 模型在犹豫/漂移（不确定），
  // 与 SU（arXiv 2609.05274）的 draft cross-likelihood 同源，只是聚合到请求级（零改动）。
  // 阶段 1 只读日志尾部，不触发额外推理；< threshold 时作为审计门控信号之一。
  specLogPath: 'D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-llama-server-autostart/llama-server-run.log',
  specAcceptanceMin: 0.65,
  // Agent-as-Judge 定向取证：审计员可请求只读取证的最大轮次（每轮 +1 LLM +1 工具）
  auditEvidenceRounds: 2,
  // P1 Critic：present 前产物质量评审（异质 rubric，每会话 ≤2 次，1 次 LLM 10-20s）
  criticEnabled: true,
  criticTimeoutMs: 90000,
  maxCriticPerSession: 2,
  // P2 Planner 检查：首次 todo 的 [VERIFY] 项是否可验证（1 次 LLM ~11s/任务）
  // verify-on-edit：每次 write/edit 后做确定性语法检查（0 LLM，仅 py/json/yaml）
  verifyOnEditEnabled: true,
  // present 前深检（import 可解析/占位符/空文件/shell 语法）：~0.3s，0 LLM
  deepCheckEnabled: true,
  plannerCheckEnabled: true,
  plannerCheckTimeoutMs: 90000,
  maxPlannerCheckPerSession: 1,
  specSignalEnabled: true
}

// ── Rubric 外置加载（JSON 单一来源；缺失则用内置默认）──
function loadRubric(name, fallback) {
  try {
    const p = `D:/Brain/workspace/bench/rubrics/${name}`
    const j = JSON.parse(readFileSync(p, 'utf8'))
    return j && typeof j === 'object' ? j : fallback
  } catch {
    return fallback
  }
}
const CRITIC_RUBRIC = loadRubric('critic_v1.json', {
  version: 'critic-builtin',
  dimensions: [
    { id: 1, name: '达标性', question: '是否覆盖任务要求的每一项？' },
    { id: 2, name: '完整性', question: '是否有空缺/占位符/截断？' },
    { id: 3, name: '可用性', question: '能直接用/跑通吗？' },
    { id: 4, name: '一致性', question: '内部有无矛盾？' },
  ],
})
const AUDIT_RUBRIC = loadRubric('audit_v1.json', { version: 'audit-builtin', checks: [], gates: [] })

// ── verify-on-edit 深度检查（present 前跑一次，~0.3s，0 LLM）──
// 1) Python 顶层 import 可解析性（find_spec 不执行模块，安全）
// 2) 占位符扫描（TODO/FIXME/pass/... 等未实现痕迹）
// 3) 空文件 / 极短文件
function checkArtifactDeep(filePath) {
  const issues = []
  if (!filePath) return issues
  try {
    const st = statSync(filePath, { throwIfNoEntry: false })
    if (!st) return issues
    if (st.size < 10) {
      issues.push('文件几乎为空（' + st.size + ' 字节）')
      return issues
    }
    // 编码检查（BOM / 非 UTF-8 字节序列）
    try {
      const head = Buffer.alloc(3)
      const fd = openSync(filePath, 'r')
      try { readSync(fd, head, 0, 3, 0) } finally { closeSync(fd) }
      if (head[0] === 0xef && head[1] === 0xbb && head[2] === 0xbf) issues.push('文件带 UTF-8 BOM（部分工具解析异常）')
      const raw = readFileSync(filePath)
      if (raw.toString('utf8').includes('\ufffd')) issues.push('文件含非法 UTF-8 序列（可能是 GBK 编码）')
    } catch { /* ignore */ }
    const lower = String(filePath).toLowerCase()
    if (lower.endsWith('.py')) {
      try {
        const script = `import ast, json, importlib.util, sys
p = sys.argv[1]
tree = ast.parse(open(p, encoding='utf-8').read())
mods = set()
for node in tree.body:
    if isinstance(node, ast.Import):
        for a in node.names:
            mods.add(a.name.split('.')[0])
    elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
        mods.add(node.module.split('.')[0])
missing = [m for m in sorted(mods) if importlib.util.find_spec(m) is None]
print(json.dumps(missing))`
        const out = execFileSync('D:/Python/python.exe', ['-c', script, filePath], { timeout: 8000, windowsHide: true, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
        const missing = JSON.parse(String(out).trim() || '[]')
        if (missing.length) issues.push('顶层 import 不可用: ' + missing.join(', '))
      } catch { /* 语法错误已由 verify-on-edit 报过，跳过 */ }
      const src = readFileSync(filePath, 'utf8')
      const ph = src.match(/^\s*(TODO|FIXME|XXX)\b.*$/gm) || []
      const passOnly = src.match(/^\s*pass\s*$/gm) || []
      if (ph.length) issues.push('占位标记 ' + ph.length + ' 处（TODO/FIXME）')
      if (passOnly.length) issues.push('空实现 pass ' + passOnly.length + ' 处')
    }
    if (lower.endsWith('.md')) {
      const src = readFileSync(filePath, 'utf8')
      const ph = src.match(/(TODO|FIXME|待补充|待填写|占位)/g) || []
      if (ph.length) issues.push('文档占位标记 ' + ph.length + ' 处')
      const heads = (src.match(/^#{1,6} /gm) || []).length
      if (heads === 0) issues.push('Markdown 无任何标题结构')
      // 重复段落检测（今晚"正文重复"的机器版）：长段落哈希重复率
      try {
        const paras = src.split(/\n\s*\n/).map((x) => x.trim()).filter((x) => x.length >= 40)
        const seen = new Map()
        let dup = 0
        for (const para of paras) {
          const key = para.slice(0, 200)
          if (seen.has(key)) dup += 1
          else seen.set(key, 1)
        }
        if (dup >= 1) issues.push('文档有 ' + dup + ' 段重复内容（首次出现后又重复）')
      } catch { /* ignore */ }
      // 路径引用检查（仅绝对路径 D:/ 或 C:/ 开头的引用）
      try {
        const refs = [...src.matchAll(/[A-Za-z]:[\\/][^\s`"'()\[\]]{4,}/g)].map((m) => m[0].replace(/[.,;:]+$/, ''))
        const missing = refs.filter((r) => !existsSync(r)).slice(0, 3)
        if (missing.length) issues.push('引用了不存在的路径: ' + missing.join(', '))
      } catch { /* ignore */ }
    }
    if (lower.endsWith('.sh')) {
      try {
        execFileSync('bash', ['-n', filePath], { timeout: 5000, windowsHide: true, encoding: 'utf8', stdio: ['ignore', 'ignore', 'pipe'] })
      } catch (e) {
        issues.push('shell 语法错误: ' + String(e?.stderr || e?.message || '').replace(/\s+/g, ' ').slice(0, 120))
      }
    }
  } catch { /* ignore */ }
  return issues
}

// ── verify-on-edit：确定性语法检查（0 LLM 成本，仅 .py/.json/.yml/.yaml）──
function checkSyntax(filePath) {
  if (!filePath) return null
  const p = String(filePath)
  const lower = p.toLowerCase()
  try {
    if (lower.endsWith('.json')) {
      JSON.parse(readFileSync(p, 'utf8'))
      return null
    }
    if (lower.endsWith('.py')) {
      // 用 python 编译检查（1 次进程，~80ms）
      const r = execFileSync('D:/Python/python.exe', ['-c', 'import py_compile,sys;py_compile.compile(sys.argv[1],doraise=True)', p], { timeout: 8000, windowsHide: true, encoding: 'utf8', stdio: ['ignore', 'ignore', 'pipe'] })
      return null
    }
    // .yml/.yaml 用 python -c yaml.safe_load（dsh 的 !!js 标签会误报，跳过 cordis 配置）
    if ((lower.endsWith('.yml') || lower.endsWith('.yaml')) && !lower.includes('cordis')) {
      execFileSync('D:/Python/python.exe', ['-c', 'import yaml,sys;yaml.safe_load(open(sys.argv[1],encoding="utf-8"))', p], { timeout: 8000, windowsHide: true, encoding: 'utf8', stdio: ['ignore', 'ignore', 'pipe'] })
      return null
    }
  } catch (e) {
    const msg = String(e?.stderr || e?.message || e).replace(/\s+/g, ' ').slice(0, 300)
    return msg || '语法检查失败'
  }
  return null
}

// ── CritBank 经验检索（模块级加载一次）──
let CRITBANK = []
try {
  CRITBANK = JSON.parse(readFileSync('D:/Brain/workspace/bench/critbank.json', 'utf8'))
} catch { /* 缺失则静默不启 */ }

function matchCritbank(s) {
  if (!Array.isArray(CRITBANK) || CRITBANK.length === 0) return []
  const trail = Array.isArray(s?.trail) ? s.trail.slice(-8) : []
  const hay = trail.map((x) => `${x?.name || ''} ${x?.result || ''} ${x?.status || ''}`).join(' ').toLowerCase()
  return CRITBANK
    .map((c) => ({ c, score: (c.tags || []).filter((t) => hay.includes(String(t).toLowerCase())).length }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 2)
    .map((x) => `【相关教训 ${x.c.id}】${x.c.lesson}`)
}

// ── MTP 信心信号（读 llama-server 日志尾部的 draft acceptance，零额外推理）──
function readSpecAcceptance(logPath) {
  try {
    const st = statSync(logPath)
    const len = Math.min(st.size, 16384)
    const buf = Buffer.alloc(len)
    const fd = openSync(logPath, 'r')
    try { readSync(fd, buf, 0, len, st.size - len) } finally { closeSync(fd) }
    const text = buf.toString('utf8')
    const m = [...text.matchAll(/draft acceptance = ([0-9.]+)/g)].pop()
    return m ? Number.parseFloat(m[1]) : null
  } catch {
    return null
  }
}


// ── turn-continuation-guard 部分（合并自 dsh-turn-continuation-guard，L0-L3）──
const DEFAULT_CONFIRM_WORDS = [
  '好', '好的', '好。', '好！', '好,', '好的，', '嗯', '嗯。', '行',
  '收到', '明白', '知道了', 'OK', 'ok', 'Okay'
]
const DEFAULT_WRITE_TOOLS = [
  'write', 'edit', 'apply_patch', 'multi_edit', 'create_file',
  'str_replace', 'write_file', 'notebook_edit'
]
const WRITE_CLAIM = /已(?:经)?(?:写入|保存|创建|生成|更新|落盘|建好|写好|放在)|保存到|写入到|写到了|生成到|written to|saved to|created file/i
const PATH_RE = /(?:[A-Za-z]:[\\/][^\s`"'））,，。；;、]+|\.\.?[\\/][^\s`"'））,，。；;、]+)/g

function deepFreeze(value) {
  if (value === null || typeof value !== 'object') return value
  for (const key of Object.keys(value)) deepFreeze(value[key])
  return Object.freeze(value)
}
function createSteeringMessage(text, sourceKind) {
  return deepFreeze({
    role: 'user',
    content: [{ type: 'text', text }],
    source: { kind: sourceKind },
    id: randomUUID()
  })
}
function summarizeAssistant(message) {
  const blocks = Array.isArray(message?.content) ? message.content : []
  let body = ''
  let toolCalls = 0
  for (const block of blocks) {
    if (block === null || typeof block !== 'object') continue
    if (block.type === 'text' && typeof block.text === 'string') body += block.text
    else if (block.type === 'tool-call') toolCalls += 1
  }
  return { body: body.trim(), toolCalls }
}
function claimedPaths(body) {
  const found = new Set()
  for (const line of body.split(/\r?\n/)) {
    if (!WRITE_CLAIM.test(line)) continue
    const matches = line.match(PATH_RE)
    if (!matches) continue
    for (const raw of matches) {
      const clean = raw.replace(/[）)\]】>»"',，。；;、]+$/, '')
      if (clean.length >= 4) found.add(clean)
    }
  }
  return [...found]
}
function longestCodeBlockLines(body) {
  let longest = 0
  const re = /```[^\n]*\n([\s\S]*?)```/g
  let match
  while ((match = re.exec(body)) !== null) {
    const lines = match[1].split(/\r?\n/).length
    if (lines > longest) longest = lines
  }
  return longest
}
function fileState(path, since) {
  try {
    if (!existsSync(path)) return { exists: false, fresh: false }
    if (since === undefined) return { exists: true, fresh: false }
    const stat = statSync(path)
    return { exists: true, fresh: stat.mtimeMs >= since - 1000 }
  } catch {
    return { exists: false, fresh: false }
  }
}
const TURN_GUARD_DEFAULTS = {
  maxContinuationsPerTurn: 1,
  maxContinuationsPerSession: 20,
  maxBodyChars: 3,
  confirmWords: DEFAULT_CONFIRM_WORDS,
  requirePriorToolCall: true,
  writeTools: DEFAULT_WRITE_TOOLS,
  checkFileClaims: true,
  blockEmptyFinish: true,
  requireFreshMtime: false,
  blockCodeWithoutWrite: true,
  minCodeLines: 20,
  message: '上一步没有产生任何动作（正文只有一个确认词，也没有调用工具）。任务还没有完成。现在直接执行下一步：调用一个与之前不同的工具，或者写出完整结论；不要只回复确认词。',
  claimMessage: '你声称已经写入 {paths}，但这个文件并不存在{detail}。不要把内容写在回复正文里当作"已落盘"。任务还没有完成：现在立刻调用写文件工具把内容写入该路径，然后再汇报。',
  codeDumpMessage: '你把完整代码写在了回复正文里，但本轮没有调用过任何写文件工具，所以文件并没有真的生成。如果任务要求产出文件，现在立刻调用 write 工具把内容落盘；如果用户只是想看代码，就明确说明"未落盘"。',
  emptyFinishMessage: '上一轮你只产生了思考，没有输出任何正文，也没有调用工具 —— 对用户来说这一轮是空的。把"想清楚了"当成"做完了"不算完成。现在二选一：任务还没完成就调用下一步真正需要的工具；已经完成就把完整结论写进正文。'
}

function rawHasKey(obj, key) {
  return obj !== null && typeof obj === 'object' && Object.prototype.hasOwnProperty.call(obj, key)
}

function createMessage(text, kind) {
  return Object.freeze({
    role: 'user',
    content: [{ type: 'text', text }],
    source: { kind },
    id: randomUUID()
  })
}

function blocksText(content) {
  if (typeof content === 'string') return content
  if (Array.isArray(content)) return content.map((b) => (b && typeof b.text === 'string') ? b.text : '').join('')
  return ''
}

export function apply(ctx, config) {
  const cfg = { ...DEFAULTS, ...TURN_GUARD_DEFAULTS }
  // normalizeConfig 只覆盖 raw 中显式给出的键——所以先改签名再手写合并：
  for (const k of Object.keys(cfg)) {
    if (rawHasKey(config, k)) cfg[k] = config[k]
  }
  for (const k of Object.keys(cfg)) {
    if (cfg[k] && typeof cfg[k] === 'object' && !Array.isArray(cfg[k]) && config && typeof config[k] === 'object' && !Array.isArray(config[k])) cfg[k] = { ...cfg[k], ...config[k] }
  }
  if (!cfg.enabled) return

  const info = (t) => { try { ctx.logger?.info?.(t) } catch { /* ignore */ } }
  const warn = (t) => { try { ctx.logger?.warn?.(t) } catch { /* ignore */ } }
  info(`audit-loop v2: 已加载（每 ${cfg.auditEverySteps} 步审计 + 纠正角色实时化）`)

  if (cfg.probePath) {
    try { writeFileSync(cfg.probePath, JSON.stringify({ loadedAt: new Date().toISOString(), version: 2, config: cfg }, null, 2)) }
    catch { /* ignore */ }
  }

  const states = new Map()
  let sessionInjections = 0

  function stateOf(id) {
    let s = states.get(id)
    if (!s) {
      s = { initial: '', step: 0, trail: [], turnInjections: 0, auditing: false,
        // turn-guard L0-L3 状态（合并）
        turn: 0, turnStartedAt: undefined, toolCalls: 0, writeCalls: 0,
        continuations: 0, totalContinuations: 0, last: undefined, sharedInjections: 0,
        // continuity 状态（initial 复用上面的字段）
        latest: '', pendingArchive: false, pendingTodoEcho: false, lastTodos: null, todoCalls: 0, sinceLastTodo: 0,
        turnTodoInjections: 0, sessionTodoInjections: 0, remindedNoTodo: false, rejectedItems: [] }
      states.set(id, s)
    }
    return s
  }

  ctx.on('session/event', (session, event) => {
    try {
      if (!session || !event) return
      const s = stateOf(session.id)
      if (event.type === 'turn/start') {
        s.turnInjections = 0
        s.trail = []
        s.lastTodoSig = null
        s.todoRedundant = 0
        // turn-guard：本轮重置（合并）
        s.turn = event.data?.turn ?? s.turn + 1
        s.turnStartedAt = Date.now()
        s.toolCalls = 0
        s.writeCalls = 0
        s.continuations = 0
        s.last = undefined
        s.sharedInjections = 0
        // continuity P1 计数重置
        s.turnTodoInjections = 0
        s.remindedNoTodo = false
        // D4 present-gate 本轮重置
        s.presentCalled = false
        s.spawnedThisTurn = false
        s.verifyRan = false
        s.presentGateCount = 0
        return
      }
      if (event.type === 'assistant/message') {
        // turn-guard：记录本轮最后的 assistant 正文与工具调用数（L0-L3 判定依据）
        s.last = summarizeAssistant(event.data?.message)
        // D5 无进展计数：上一步没有生产性调用（write/edit/todo_write）则 +1，否则清零
        s.noProgressSteps = s.lastStepProductive ? 0 : (s.noProgressSteps || 0) + 1
        s.lastStepProductive = false
        return
      }
      if (event.type === 'compaction/prune' || event.type === 'compaction/summary') {
        // D5：压缩后是状态重建高危期，标记一次（审计门控会在此触发一次）
        s.justCompacted = true
        s.pendingArchive = true
        return
      }
      if (event.type === 'user/message' && event.data?.source?.kind === 'user') {
        const t = blocksText(event.data.content).trim()
        if (t && !t.startsWith('<system-reminder>')) {
          if (!s.initial) s.initial = t.slice(0, 400)
          s.latest = t.slice(0, 1000)
        }
        return
      }
      // v3.3 todo/write 观测：冗余更新检测（与上次 todos 内容完全一致 = 无意义调用）
      if (event.type === 'todo/write') {
        try {
          const todos = event.data?.todos
          const sig = JSON.stringify(todos)
          const arr = Array.isArray(todos) ? todos : []
          const done = arr.filter((x) => x && x.status === 'completed').length
          s.todos = arr  // 供 present 前"交付物清单对照"使用
          if (Array.isArray(arr) && arr.length > 0) {
            s.lastTodos = arr
            s.pendingTodoEcho = true
          }
          // P2 Planner 检查：首次出现 [VERIFY] 项时标记（pre-step 里跑一次可验证性检查）
          if (s.plannerChecked !== true && cfg.plannerCheckEnabled) {
            const verifyItems = arr.filter((t) => String(t?.content ?? '').includes('[VERIFY]'))
            if (verifyItems.length) {
              s.pendingPlannerCheck = verifyItems.map((t) => String(t.content).slice(0, 200))
            }
          }
          s.trail.push({ kind: 'todo', name: 'todo', args: sig.slice(0, 200), fullArgs: sig, step: s.step,
            status: 'OK', result: arr.length + '项(完成' + done + ') ' + String(arr[0]?.content || '').slice(0, 60) })
          if (s.trail.length > 40) s.trail.shift()
          // D3：与上次完全相同的冗余更新 >= 2 次 → 提醒
          if (s.lastTodoSig === sig) {
            s.todoRedundant = (s.todoRedundant || 0) + 1
            if (s.todoRedundant >= 2 && !s.pendingInject) {
              s.pendingInject = '[harness 系统修正] todo 清单已连续 ' + (s.todoRedundant + 1) + ' 次写入且内容完全无变化——状态没有任何推进。请停止重复更新清单：要么推进某个 in_progress 项的实际工作，要么结束本轮汇报。'
              info(`behavior-guard: D3 冗余 todo 更新命中 (${s.todoRedundant + 1} 次)`)
            }
          } else {
            s.todoRedundant = 0
          }
          s.lastTodoSig = sig
        } catch (e) { warn(`behavior-guard: todo 事件处理失败 ${String(e)}`) }
        return
      }
      if (event.type === 'step/end') {
        s.sinceLastTodo = (s.sinceLastTodo || 0) + 1
        return
      }
      if (event.type === 'tool/call') {
        // turn-guard：工具调用计数 + writeTools 计数（L2/L3 判定依据）
        s.toolCalls += 1
        if (cfg.writeTools.includes(String(event.data?.name ?? ''))) s.writeCalls += 1
        const fullArgs = String(event.data?.arguments ?? '')
        // D4 present-gate：验收痕迹观测（present / spawn 验收者 / 跑过 verify_agent）
        {
          const callName = String(event.data?.name ?? '')
          if (callName === 'present') s.presentCalled = true
          if (callName === 'spawn_teammate') s.spawnedThisTurn = true
          if (callName === 'pwsh' && fullArgs.includes('verify_agent')) s.verifyRan = true
          // D5 生产性调用标记（写/编辑/todo 更新 = 有进展）
          if (callName === 'write' || callName === 'edit' || callName === 'todo_write') s.lastStepProductive = true
          // continuity P1：todo 调用计数
          if (callName === 'todo_write') {
            s.todoCalls = (s.todoCalls || 0) + 1
            s.sinceLastTodo = 0
          }
        }
        s.trail.push({ kind: 'call', name: String(event.data?.name ?? ''), args: fullArgs.slice(0, 200), fullArgs, step: event.data?.step })
        if (s.trail.length > 40) s.trail.shift()
        // v3.2 代验收：记录 spawn_teammate 携带的验收标准（prompt/description），并继承最近产物
        if (event.data?.name === 'spawn_teammate') {
          let a = {}
          try { a = JSON.parse(fullArgs || '{}') } catch { /* ignore */ }
          s.verifyContext = { criteria: String(a.prompt || a.description || '').slice(0, 500), waitBad: 0, product: s.lastProduct }
          info(`audit-loop: spawn 收到，验收上下文 product=${s.verifyContext.product || '(无)'}`)
        }
        return
      }
      if (event.type === 'tool/result') {
        const c = s.trail.filter((x) => x.kind === 'call').pop()
        const txt = blocksText(event.data?.message?.content)
        // v3.1 三档状态（第二轮实测：wait 超时/glob 空结果曾被误标 OK，审计漏检）
        let status = 'OK'
        if (txt.startsWith('Error:') || txt.startsWith('[stderr]') || txt.includes(': not found') || txt.includes('ParserError') || txt.startsWith('Traceback')) {
          status = 'FAIL'
        } else if (
          txt.includes('"timedOut":true') || txt.includes("'timedOut': True") ||
          (c && c.name === 'glob' && txt.trim().length < 3) ||
          /no (files|results|matches)/i.test(txt.slice(0, 120))
        ) {
          status = 'UNPRODUCTIVE' // 非生产性：超时/空结果——不算崩溃但无进展
        }
        if (c) {
          c.ok = status === 'OK'
          c.status = status
          // v2：证据类工具的成功结果保留全文（纠正器的定位依据）
          const isEvidence = cfg.evidenceTools.includes(c.name) && status === 'OK'
          c.result = txt.slice(0, isEvidence ? cfg.evidenceMaxChars : 80).replace(/\s+/g, ' ')
          if (isEvidence) c.fullEvidence = true
          // v3.2 代验收：write/edit 成功 = 记录最近产物路径（spawn 时继承）
          if (status !== 'OK' && c) {
            const item = `${c.name}(${String(c.args || '').slice(0, 90)}) → ${String(txt || '').slice(0, 80)}`
            if (!s.rejectedItems.some((x) => x.slice(0, 120) === item.slice(0, 120))) {
              s.rejectedItems.push(item)
              if (s.rejectedItems.length > 6) s.rejectedItems.shift()
            }
          }
          if (status === 'OK' && (c.name === 'write' || c.name === 'edit')) {
            try {
              const a = JSON.parse(c.fullArgs || c.args || '{}')
              if (a.file_path) s.lastProduct = String(a.file_path)
            } catch { /* ignore */ }
            // ── verify-on-edit（确定性语法检查，0 LLM 成本）──
            // 依据：Qwen3.5-35B scaffold 实验——每次编辑后验证 vs 只做末次验证：
            // SWE-bench Verified Hard 22.2% → 37.8%（+15.6pp）；9B 换 scaffold 19.11%→45.56%。
            // 确定性修复在 LLM 循环外（tech4talk："deterministic fixups outside the inference loop"）。
            if (cfg.verifyOnEditEnabled) {
              const syntaxErr = checkSyntax(s.lastProduct)
              if (syntaxErr) {
                s.pendingInject = '[harness 语法检查] 刚写入的文件有语法错误：' + syntaxErr +
                  '\n修复该语法错误后继续（不要跳过——后续步骤都会基于坏文件）。'
                info(`behavior-guard: verify-on-edit 发现语法错误 ${s.lastProduct}: ${String(syntaxErr).slice(0, 60)}`)
              }
            }
          }
          // wait 连续超时计数（spawn 之后）
          try { writeFileSync('D:/llama.cpp/_trace.log', 'result ' + c.name + ' status=' + status + ' ctx=' + (s.verifyContext ? ('wB=' + s.verifyContext.waitBad + ' prod=' + s.verifyContext.product) : 'NULL') + ' lastProd=' + s.lastProduct + '\n', { flag: 'a' }) } catch { }
          if (c.name === 'wait_agent' && s.verifyContext) {
            if (status === 'UNPRODUCTIVE') s.verifyContext.waitBad += 1
            else s.verifyContext.waitBad = 0
            if (s.verifyContext.waitBad >= cfg.verifyMinWaits && s.verifyContext.product && !s.pendingVerify) {
              s.pendingVerify = { product: s.verifyContext.product, criteria: s.verifyContext.criteria }
              s.verifyContext.waitBad = 0
              info(`audit-loop: v3.2 spawn 验收 wait 连续 ${cfg.verifyMinWaits} 次超时 → 触发代验收 (${s.pendingVerify.product})`)
            }
          }
          // v3.1 确定性信号（代码判定，不等审计窗口）：
          // D1 同名调用总数>=3 且其中 FAIL/UNPRODUCTIVE >= 2 → 重复探测无进展
          // D2 同参数 FAIL >= 2 → 交给纠正器产出修正包
          const sameNameCalls = s.trail.filter((x) => x.kind === 'call' && x.name === c.name)
          const sameNameBad = sameNameCalls.filter((x) => x.status === 'UNPRODUCTIVE' || x.status === 'FAIL').length
          const tail = s.trail.filter((x) => x.kind === 'call').slice(-2)
          const sameArgsDoubleFail = tail.length === 2 &&
            tail.every((x) => x.status === 'FAIL' && x.name === c.name && x.args === c.args)
          if (sameNameCalls.length >= 3 && sameNameBad >= 2 && !s.pendingInject) {
            s.pendingInject = `[harness 系统修正] 检测到 ${c.name} 已调用 ${sameNameCalls.length} 次、其中 ${sameNameBad} 次超时或无结果。重复探测不是进展——请停止该循环：若在等子智能体结论，其完成后会自动回注（可先输出阶段性报告结束本轮）；若是查询类，换方法（es.exe / 精确短路径）或问用户。`
            info(`audit-loop: D1 重复探测命中 (${c.name} x${sameNameCalls.length}, bad=${sameNameBad})`)
          } else if (sameArgsDoubleFail && !s.pendingCorrector) {
            s.pendingCorrector = true
            info(`audit-loop: D2 同参数双重失败命中 (${c.name})`)
          }
        }
        return
      }
    } catch (error) { warn(`audit-loop: event 处理失败 ${String(error)}`) }
  })

  function buildTrailText(s) {
    const calls = s.trail.filter((x) => x.kind === 'call' || x.kind === 'todo')
    // v3.1：连续同名调用 run（重复探测信号，如 wait_agent ×3）
    const runByIndex = []
    let run = 1
    for (let i = 1; i <= calls.length; i++) {
      if (i < calls.length && calls[i].name === calls[i - 1].name) { run++; runByIndex[i - 1] = run }
      else { if (run >= 3) runByIndex[i - 1] = run; run = 1; runByIndex[i - 1] = runByIndex[i - 1] || 1 }
    }
    const lines = calls.map((x, i) => {
      const st = x.status || (x.ok === undefined ? '?' : (x.ok ? 'OK' : 'FAIL'))
      const rl = runByIndex[i] || 1
      const runMark = rl >= 3 ? ` [连续第${rl}次]` : ''
      return `step${x.step} ${x.name}(${(x.args || '').slice(0, 80)}) -> ${st}${runMark} | ${x.result || ''}`
    }).filter(Boolean)
    return lines.join('\n').slice(-4000)
  }

  const AUDIT_PROMPT = (task, trail, evidLog) => `你是独立会话审计员，没有参与这段 agent 工作。只依据以下事实判断，不要猜测。

【任务】${task || '(未知)'}

【最近工具轨迹（状态三档：OK=有进展 / FAIL=报错 / UNPRODUCTIVE=超时或空结果无进展）】
${trail}${evidLog && evidLog.length ? `

【你已取证的证据（只读代执行结果）】
${evidLog.map((e, i) => `证据${i + 1}: ${e.req}\n→ ${e.result}`).join('\n---\n')}` : ''}

检查以下问题（规则来自 ${AUDIT_RUBRIC.version} 手册；只报上面事实能直接支撑的）：
${(AUDIT_RUBRIC.checks || []).map((c) => `${c.id}. ${c.name}：${c.description}${c.deterministic ? '  ← 系统已用 ' + c.deterministic + ' 确定性检测覆盖，你专注语义层面，不要重复报告已知的重复调用。' : ''}`).join('\n')}

如需更多证据才能判断（最多请求一次），可请求只读取证：
{"verdict":"NEED_EVIDENCE","tool":"glob 或 read","args":{...},"reason":"一句话说明需要什么证据"}

只输出 JSON（无其他文字）。判定参考下面的实例（照这个形状输出）：

实例1（重复失败）：
{"verdict":"ISSUE","issue":"step5: glob 同参数连续第3次，结果与前两次相同","fix":"停止 glob 重试，直接 read step3 结果里的 state.json"}

字段纪律：issue 必须以 stepN: 开头（引用具体步骤）；fix 只写**一个可执行动作**（动词开头，
不含"或者/二选一"这类多选建议）——执行者照做即可。

实例2（证据不足——拿不准就输出这个，别硬判）：
{"verdict":"UNCERTAIN","reason":"轨迹里看不到 write 的结果，无法判断产物是否落盘"}

实例3（正常）：
{"verdict":"OK"}`

  const CORRECTOR_PROMPT = (task, failDetail, evidence) => `你是独立纠正器。主 agent 在执行任务时陷入重复失败，你来依据环境事实确定正确的下一步参数。你没有参与之前的工作，只能依据下面给出的证据。

【任务】${task || '(未知)'}

【反复失败的调用】
${failDetail}

【环境证据：成功调用返回的完整结果（正确答案很可能就在其中）】
${evidence || '(无证据可用)'}

请从证据中定位正确目标，并输出 JSON（无其他文字）：
{"action":"retry_with","tool":"工具名","args":{...完整的调用参数对象...},"reason":"依据证据的一句话理由"}
或无法从证据确定时：
{"action":"ask_user","reason":"证据不足，需要用户澄清什么（一句话）"}
或证据表明该目标不存在：
{"action":"abandon","reason":"一句话"}

输出要求（正面表述）：
- args 照抄证据里出现过的调用格式：read 用 {file_path}，glob 用 {pattern}，shell 工具用 {command}——
  与证据中的实际调用一字一致（含完整字符串、引号、反斜杠）。
- 严格 JSON 对象，所有字段写全（把示例里的省略号处写成实际值）。
路径规则（2026-11-17 实证）：**路径原样复制证据文本里的那一段**（逐字符），
证据里没有可用路径时输出 ask_user 或 abandon——你给出的每个路径都应该是证据里出现过的原文。`

  async function callLLM(prompt, maxTokens, timeoutMs) {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), timeoutMs)
    try {
      const resp = await fetch(cfg.endpoint, {
        method: 'POST',
        body: JSON.stringify({
          model: cfg.model,
          messages: [{ role: 'user', content: prompt }],
          max_tokens: maxTokens, temperature: 0.0, top_k: 1,
        }),
        headers: { 'Content-Type': 'application/json' },
        signal: ctrl.signal,
      })
      clearTimeout(timer)
      const data = await resp.json()
      let out = (data?.choices?.[0]?.message?.content || '').trim()
      if (out.startsWith('```')) {
        out = out.replace(/^```(?:json)?/, '').replace(/```$/, '').trim()
      }
      const i = out.indexOf('{')
      const j = out.lastIndexOf('}')
      if (i < 0 || j <= i) return null
      return JSON.parse(out.slice(i, j + 1))
    } catch (error) {
      clearTimeout(timer)
      warn(`audit-loop: LLM 调用失败 ${String(error)}`)
      return null
    }
  }

  async function runAudit(s) {
    const trail = buildTrailText(s)
    if (!trail) return null
    // ── Agent-as-Judge 定向取证（2026-11-17，文献驱动）──
    // 依据：Agent-as-a-Judge（arXiv 2410.10934）+ 生产实践（证据预算/动作预算/早停）。
    // 审计员可输出 NEED_EVIDENCE + 只读工具请求，插件确定性代执行后回喂——最多 N 轮、
    // 只读白名单、总超时受 auditTimeoutMs 约束。成本：每轮 +1 次 LLM（5-15s）+ 1 次工具。
    const rounds = cfg.auditEvidenceRounds ?? 2
    const evidLog = []
    for (let round = 0; round < rounds; round++) {
      const out = await callLLM(AUDIT_PROMPT(s.initial, trail, evidLog), 600, cfg.auditTimeoutMs)
      if (!out || out.verdict !== 'NEED_EVIDENCE') return out
      if (round === rounds - 1) {
        // 取证轮次用尽仍要证据 → 视为弃权（不介入，记录）
        info(`audit-loop: 取证轮次用尽 → 弃权（${String(out.reason || '').slice(0, 50)}）`)
        return { verdict: 'UNCERTAIN', reason: 'evidence-budget-exhausted: ' + String(out.reason || '') }
      }
      // 只读白名单 + 限频：仅 read/glob/grep/list_agents；每次一轮一调用
      const pkg = { action: 'retry_with', tool: String(out.tool || ''), args: out.args || {} }
      const exec = cfg.executorEnabled ? executeReadOnly(pkg) : null
      evidLog.push({
        req: `${out.tool} ${JSON.stringify(out.args || {}).slice(0, 120)}`,
        result: exec && exec.ok ? String(exec.content || '').slice(0, 1200) : ('取证失败: ' + String(exec?.error || 'executor disabled')),
      })
      info(`audit-loop: 审计员请求取证 ${out.tool} → ${exec && exec.ok ? '成功' : '失败'}（第 ${round + 1} 轮）`)
    }
    return null
  }

  /** v2 纠正器：从失败详情 + 成功证据产出修正包 */
  function collectCorrectorInput(s) {
    const fails = s.trail.filter((x) => x.kind === 'call' && x.ok === false)
    const evid = s.trail.filter((x) => x.kind === 'call' && x.ok === true && x.fullEvidence)
    const failDetail = fails.slice(-4).map((x) =>
      `step${x.step} ${x.name} 参数=${x.args}\n  错误=${(x.result || '').slice(0, 150)}`).join('\n')
    const evidence = evid.map((x) =>
      `step${x.step} ${x.name}(${(x.args || '').slice(0, 100)}) 返回：\n${x.result}`).join('\n---\n')
    return { failDetail, evidence }
  }

  // ── P2 Planner 检查：首次 [VERIFY] 项是否"可验证"（1 次 LLM，每会话 1 次）──
  const PLANNER_PROMPT = (task, items) => `你是计划评审（Planner 视角）。判断下面任务的验收项是否"可验证"。

【任务】${task || '(未知)'}

【验收项】
${items.map((x, i) => `${i + 1}. ${x}`).join('\n')}

"可验证" = 能由命令/文件/阈值/输出直接判定（如"运行 agentlab 7/7 通过"、"文件存在且含 X 段"）。
"不可验证" = 只有感受性描述（如"确认功能正常"、"确保质量良好"）。

只输出 JSON（无其他文字）：
{"verdict":"OK"}
或
{"verdict":"UNVERIFIABLE","items":["第2项：'确保质量良好'——改写为具体判据"],"fix":"一句话给出更可验证的写法"}`
  async function runPlannerCheck(s) {
    const items = s.pendingPlannerCheck
    if (!Array.isArray(items) || items.length === 0) return null
    return callLLM(PLANNER_PROMPT(s.initial, items), 400, cfg.plannerCheckTimeoutMs || 90000)
  }

  // ── P1 Critic：产物质量评审（异质 rubric；只读产物，不看执行过程）──
  const CRITIC_PROMPT = (task, product, content) => `你是独立的产物评审员（Critic）。你只评审产物本身，不看执行过程，也没有参与制作。

【任务要求】${task || '(未知)'}

【产物】${product}

【产物内容】
${content}

按以下维度各判一行（达标 / 不达标 / 无法判断）：
${(CRITIC_RUBRIC.dimensions || []).map((d) => `${d.id}. ${d.name}：${d.question}${d.fail_example ? '（反例：' + d.fail_example + '）' : ''}`).join('\n')}

只输出 JSON（无其他文字）：
{"verdict":"ACCEPT","reasons":["1 达标","2 达标","3 达标","4 达标"]}
或
{"verdict":"REJECT","reasons":["3 不达标: 缺少 main 入口"],"fix":"一句最关键的修正动作"}
或
{"verdict":"UNCERTAIN","reasons":["无法判断: 产物内容为空"]}`

  async function runCritic(s) {
    const product = s.lastProduct
    if (!product) return null
    let content = ''
    try {
      const st = statSync(product, { throwIfNoEntry: false })
      if (!st || !st.isFile()) return null
      content = readFileSync(product, 'utf8').slice(0, 3000)
    } catch {
      return null
    }
    if (!content.trim()) return null
    return callLLM(CRITIC_PROMPT(s.initial, product, content), 500, cfg.criticTimeoutMs || 90000)
  }

  async function runCorrector(s) {
    const { failDetail, evidence } = collectCorrectorInput(s)
    if (!failDetail) return null
    return callLLM(CORRECTOR_PROMPT(s.initial, failDetail, evidence), 800, cfg.correctorTimeoutMs)
  }

  // v3.2 代验收：直接跑 verify_agent.py（三态环境判定），不等回注
  function runVerifyAgent(product, criteria) {
    return new Promise((resolve) => {
      try {
        const args = [cfg.verifyScript, product, criteria || '产物存在且内容完整准确']
        execFile(cfg.pythonPath, args, { windowsHide: true, timeout: cfg.verifyTimeoutMs, maxBuffer: 1024 * 1024 },
          (err, stdout, stderr) => {
            try {
              // verify_agent.py --json 输出 JSON；普通模式输出 [PASS]/[FAIL]/[INCONCLUSIVE] 行
              const out = String(stdout || '')
              const j = out.indexOf('{')
              if (j >= 0) {
                try { return resolve(JSON.parse(out.slice(j, out.lastIndexOf('}') + 1))) } catch { /* fallthrough */ }
              }
              const m = out.match(/\[(PASS|FAIL|INCONCLUSIVE)\]\s*(.*)/)
              if (m) return resolve({ verdict: m[1], reason: m[2] })
              resolve({ verdict: 'INCONCLUSIVE', reason: (err && err.message) || (stderr || out).slice(0, 100) })
            } catch (e) { resolve({ verdict: 'INCONCLUSIVE', reason: String(e) }) }
          })
      } catch (e) { resolve({ verdict: 'INCONCLUSIVE', reason: String(e) }) }
    })
  }

  function formatCorrection(pkg) {
    if (pkg.action === 'retry_with' && pkg.tool) {
      const argsStr = JSON.stringify(pkg.args ?? {}, null, 0)
      return `[harness 系统修正] 独立纠正器依据环境证据确定了正确参数（理由：${pkg.reason || '见证据'}）。请原样调用：${pkg.tool}，参数：${argsStr}。这是一次性的参数修正——调用时不要改动任何字段。`
    }
    if (pkg.action === 'ask_user') {
      return `[harness 系统修正] 独立纠正器认为环境证据不足以继续，需要用户澄清：${pkg.reason || '请向用户确认下一步。'}请立即向用户提问。`
    }
    if (pkg.action === 'abandon') {
      return `[harness 系统修正] 独立纠正器依据环境证据判定该目标不可达：${pkg.reason || '目标不存在'}。停止尝试，从任务清单中移除该项并向用户说明。`
    }
    return null
  }

  // ---- v3 代执行器：只读操作确定性执行（ReWOO Worker 的插件版）----
  // 构造性消除传递损耗：主模型不抄参数、不重调用，直接消费执行结果。
  // 边界：仅只读（read/glob 的受限子集）；路径必须落在 allowedRoots 内；
  //       写操作永远走 v2 指令注入（守卫 L1 哲学：写必须由主模型做且可验证）。

  function resolveSafePath(rawPath) {
    if (typeof rawPath !== 'string' || !rawPath.trim()) return null
    let p = rawPath.trim().replace(/\\/g, '/')
    // 剥掉可选的 file:// 前缀与两侧引号
    p = p.replace(/^file:\/\//, '').replace(/^["']|["']$/g, '')
    const isAbs = /^[a-zA-Z]:\//.test(p) || p.startsWith('//')
    let full
    if (isAbs) {
      full = p
    } else {
      full = cfg.workspaceRoot.replace(/\/$/, '') + '/' + p
    }
    const norm = path.normalize(full).replace(/\\/g, '/')
    // 路径逃逸校验：归一化后必须仍在某个允许根内
    const allowed = cfg.allowedRoots.some((r) => {
      const nr = path.normalize(r).replace(/\\/g, '/').replace(/\/$/, '')
      return norm === nr || norm.startsWith(nr + '/')
    })
    if (!allowed) return null
    return norm
  }

  function executeReadOnly(pkg) {
    try {
      if (pkg.tool !== 'read' && pkg.tool !== 'glob') return null
      const args = pkg.args ?? {}
      const target = resolveSafePath(args.file_path ?? args.path ?? args.pattern ?? '')
      if (!target) return { ok: false, error: '路径不在允许的根目录内（安全边界拒绝）' }
      const st = statSync(target, { throwIfNoEntry: false })
      if (!st) return { ok: false, error: '目标不存在: ' + target }
      if (st.isDirectory() || pkg.tool === 'glob') {
        // 受限列目录：单层，不做递归通配（避免大目录扫描）
        const items = readdirSync(target).slice(0, 200)
        return { ok: true, kind: 'list', target, content: items.join('\n') }
      }
      if (st.size > 2 * 1024 * 1024) return { ok: false, error: '文件过大（>2MB），拒绝代读' }
      const body = readFileSync(target, 'utf-8')
      const cut = body.length > cfg.executorMaxChars
        ? body.slice(0, cfg.executorMaxChars) + `\n…[截断，全文共 ${body.length} 字符]`
        : body
      return { ok: true, kind: 'read', target, content: cut, truncated: body.length > cfg.executorMaxChars }
    } catch (error) {
      return { ok: false, error: String(error) }
    }
  }

  function formatExecutorResult(pkg, exec) {
    const argsStr = JSON.stringify(pkg.args ?? {}, null, 0)
    if (!exec.ok) {
      // 代执行失败（安全边界/目标不存在）→ 降级注入。
      // ⚠ 2026-11-17 实证修正：此前把纠正器猜的路径原样写进上下文（"目标不存在 <猜测路径>"），
      // 该失败信息成为干扰源（会话里注入后模型反而进入重问循环）。现在只给方向性指引，
      // 不把未经验证的猜测路径写进上下文。
      return `[harness 系统修正] 独立纠正器认为你陷入了「${exec.error && String(exec.error).includes('不存在') ? '目标定位错误' : pkg.tool + ' 调用方式问题'}」（理由：${pkg.reason || '见证据'}）。` +
        `不要原样重试上一次调用：换一种方法核实目标（glob 搜工作区 / es.exe 全盘搜索 / 用已知短路径重新定位），或向用户确认目标位置。`
    }
    if (exec.kind === 'list') {
      return `[harness 系统修正+代执行] 独立纠正器确定了正确目标（${pkg.reason || '见证据'}），且已代为执行目录列举，结果如下。\n目录：${exec.target}\n内容：\n${exec.content}\n\n请基于以上事实继续任务——无需重新调用工具，也不要改动正确参数。`
    }
    return `[harness 系统修正+代执行] 独立纠正器确定了正确参数（理由：${pkg.reason || '见证据'}），且已代为执行读取。\n参数：${argsStr}\n结果${exec.truncated ? '（已截断）' : ''}：\n${exec.content}\n\n请基于以上内容继续任务——该文件内容已在上下文中，无需重新读取；后续引用该路径时使用 ${argsStr} 中的短路径形式。`
  }

  // ── turn-guard L0-L3：turn-stopping 时机判定（合并自 dsh-turn-continuation-guard）──
  function guardDecide(state) {
    try { writeFileSync('D:/llama.cpp/_dbg.log', 'guardDecide: last=' + JSON.stringify(state.last) + ' toolCalls=' + state.toolCalls + ' wC=' + state.writeCalls + ' cont=' + state.continuations + ' maxC=' + cfg.maxContinuationsPerTurn + ' blockEmpty=' + cfg.blockEmptyFinish + '\n') } catch (e) { try { writeFileSync('D:/llama.cpp/_dbg.log', 'trace-err ' + e + '\n', {flag:'a'}) } catch {} }
    const last = state.last
    if (last === undefined) return null
    if (last.toolCalls > 0) return null
    const body = last.body

    // L0：想完不干（正文为空、无任何工具调用）
    if (body.length === 0) {
      if (!cfg.blockEmptyFinish) return null
      return { layer: 'L0', text: cfg.emptyFinishMessage }
    }

    // L1：声称写入的文件必须真实存在（环境级判定，最硬）
    if (cfg.checkFileClaims) {
      const paths = claimedPaths(body)
      if (paths.length > 0) {
        const bad = []
        for (const path of paths) {
          const fs1 = fileState(path, state.turnStartedAt)
          if (!fs1.exists) bad.push({ path, why: '（该路径不存在）' })
          else if (cfg.requireFreshMtime && !fs1.fresh) bad.push({ path, why: '（文件存在但本轮没有被修改）' })
        }
        if (bad.length > 0) {
          const list = bad.map((x) => x.path).join('、')
          const detail = bad.length === 1 ? bad[0].why : ''
          return { layer: 'L1', text: cfg.claimMessage.replace('{paths}', list).replace('{detail}', detail) }
        }
        return null // 声明可信，放行
      }
    }

    // L2：大段代码贴正文，但本轮没写过文件
    if (cfg.blockCodeWithoutWrite && state.writeCalls === 0 && state.toolCalls > 0) {
      const lines = longestCodeBlockLines(body)
      if (lines >= cfg.minCodeLines) return { layer: 'L2', text: cfg.codeDumpMessage }
    }

    // L3：短确认词
    const degenerate = body.length <= cfg.maxBodyChars || cfg.confirmWords.includes(body)
    if (!degenerate) return null
    if (cfg.requirePriorToolCall && state.toolCalls === 0) return null
    return { layer: 'L3', text: cfg.message }
  }

  ctx.on('agent/turn-stopping', async ({ agent, turn } = {}) => {
    try {
      if (agent === undefined || agent.session === undefined) return
      const sessionId = agent.session.id
      const state = states.get(sessionId)
      if (state === undefined) return

      if (state.continuations >= cfg.maxContinuationsPerTurn) return
      if (state.totalContinuations >= cfg.maxContinuationsPerSession) return

      // ── present 前确定性深检（独立于 Critic 开关：~0.3s，0 LLM）──
      if (cfg.deepCheckEnabled && state.presentCalled === true && state.deepChecked !== true) {
        state.deepChecked = true
        try {
          const deepIssues = checkArtifactDeep(state.lastProduct)
          // 交付物清单对照：todo 里未完成的 [VERIFY] 项（声明了验收却没做）
          try {
            const pendingVerify = (Array.isArray(state.todos) ? state.todos : [])
              .filter((t) => String(t?.content ?? '').includes('[VERIFY]') && t?.status !== 'completed')
            if (pendingVerify.length) {
              deepIssues.push('清单中的验收项尚未完成：' + pendingVerify.slice(0, 2).map((t) => String(t.content).slice(0, 60)).join('；'))
            }
          } catch { /* ignore */ }
          if (deepIssues.length) {
            info(`behavior-guard: [深检] ${deepIssues.length} 项问题 — ${deepIssues.join(' | ').slice(0, 120)}`)
            state.sharedInjections += 1
            agent.steer(createSteeringMessage(
              '[harness 产物深检] 交付前确定性检查发现问题：' + deepIssues.join('；') +
              '。先修正这些问题再 present（占位符/空实现/缺失依赖/未完成验收项都会让产物不可用）。',
              'behavior-guard'
            ))
            return
          }
        } catch { /* 深检失败不阻断 */ }
      }

      // ── P1 Critic：present 前的产物质量评审（异质 rubric，与过程审计不同视角）──
      // 依据：四角色标准（Planner/Executor/Critic/Verifier）中 Critic 是"对照意图评产物质量"；
      // Apple 2026：异质 rubric 才能产生独立信号（同 rubric 重复=伪多样性）。
      // 成本：1 次 LLM（10-20s），每会话 ≤2 次，只在 present 触发。
      if (
        cfg.criticEnabled &&
        state.presentCalled === true &&
        state.criticAccepted !== true &&
        (state.criticCount || 0) < cfg.maxCriticPerSession
      ) {
        state.criticCount = (state.criticCount || 0) + 1
        try {
          const critic = await runCritic(state)
          if (critic && critic.verdict === 'ACCEPT') {
            state.criticAccepted = true
            info(`behavior-guard: [Critic] ACCEPT session=${sessionId}`)
          } else if (critic && critic.verdict === 'REJECT') {
            state.sharedInjections += 1
            agent.steer(createSteeringMessage(
              '[harness 产物评审 C-REJECT] 独立评审员（只看产物不看过程）判定产物未达验收要求：' +
              (Array.isArray(critic.reasons) ? critic.reasons.join('；') : String(critic.reasons || '')) +
              '。最关键的修正：' + String(critic.fix || '补齐未达标项后重新交付') +
              '。修正后再 present。',
              'behavior-guard'
            ))
            info(`behavior-guard: [Critic] REJECT session=${sessionId} — ${String(critic.fix || '').slice(0, 60)}`)
            return
          } else {
            info(`behavior-guard: [Critic] UNCERTAIN session=${sessionId}（回退验收闸门）`)
          }
        } catch { /* 评审失败不阻断 */ }
      }

      // ── D4 present-gate：present 声明交付但本轮无独立验收痕迹（verify-gated completion）──
      if (
        cfg.presentGateEnabled &&
        state.presentCalled === true &&
        state.criticAccepted !== true &&
        state.spawnedThisTurn !== true &&
        state.verifyRan !== true &&
        (state.presentGateCount || 0) < cfg.maxPresentGatePerTurn &&
        (state.presentGateTotal || 0) < cfg.maxPresentGatePerSession
      ) {
        state.presentGateCount = (state.presentGateCount || 0) + 1
        state.presentGateTotal = (state.presentGateTotal || 0) + 1
        state.sharedInjections += 1
        agent.steer(createSteeringMessage(
          '[harness 交付闸门] 你刚刚用 present 声明交付，但本轮没有独立验收痕迹（没有 spawn 验收者，也没有运行 verify_agent.py）。' +
          '做的人不能自己签字：实测里小模型自检只能把虚假完成率从 12.7% 降到 11.8%（同一盲区，自检无效）。' +
          '现在二选一：(1) 调用 spawn_teammate 让独立验收者按验收协议检查，或直接运行 verify_agent.py' +
          '（验收标准引用 todo 清单里的 [VERIFY] 项，逐条对照）；' +
          '(2) 明确说明本产物为什么不需要独立验收（例如纯信息性回复）。不要直接结束。',
          'behavior-guard'
        ))
        info(`behavior-guard: [D4] present-gate 拦截 session=${sessionId}（present 无独立验收痕迹）`)
        return
      }

      const verdict = guardDecide(state)
      if (verdict === null) return

      state.continuations += 1
      state.totalContinuations += 1
      state.sharedInjections += 1

      agent.steer(createSteeringMessage(verdict.text, 'behavior-guard'))
      info(
        `behavior-guard: [${verdict.layer}] 拦截 session=${sessionId} turn=${turn ?? state.turn} ` +
        `body=${JSON.stringify(state.last.body.slice(0, 60))} 本轮第 ${state.continuations} 次继续`
      )
    } catch (error) {
      // 约定：插件失败只记录，绝不结束轮次。
      warn(`behavior-guard: turn-stopping 处理失败: ${String(error)}`)
    }
  })

  ctx.on('agent/pre-step', async ({ agent } = {}, next) => {
    const decision = await next()
    try {
      if (!agent) return decision
      const s = stateOf(agent.session?.id)
      if (!s || s.auditing) return decision
      s.step += 1

      // ── continuity P0/P1.5/P1（任务连续性，2026-11-18 合并自 dsh-task-continuity）──
      if (cfg.continuityEnabled) {
        // P0：压缩后重注入任务存档（最高优先级）
        if (s.pendingArchive && s.initial) {
          const parts = [cfg.archiveHeader]
          parts.push('【初始任务】' + s.initial)
          if (s.latest && s.latest !== s.initial) parts.push('【最新用户指令】' + s.latest)
          try {
            const todos = Array.isArray(s.lastTodos) ? s.lastTodos : []
            const verifyItems = todos.filter((t) => String(t?.content ?? '').includes('[VERIFY]'))
            const doneItems = todos.filter((t) => t?.status === 'completed')
            const openItems = todos.filter((t) => t?.status !== 'completed')
            if (verifyItems.length) parts.push('【任务合同】' + verifyItems.map((t) => String(t.content).replace('[VERIFY]', '').trim()).join('；'))
            if (doneItems.length) parts.push('【已验证决策】' + doneItems.slice(0, 8).map((t) => String(t.content).slice(0, 40)).join('；'))
            if (openItems.length) parts.push('【开放问题】' + openItems.slice(0, 8).map((t) => (t?.status === 'in_progress' ? '◐' : '☐') + String(t.content).slice(0, 40)).join('；'))
            if (Array.isArray(s.rejectedItems) && s.rejectedItems.length) parts.push('【已排除】' + s.rejectedItems.slice(-5).join('\n'))
            parts.push('【压缩后自检】先回答三问再继续：①要完成什么？②已经证明了什么？③下一个安全的动作是什么？')
            try {
              appendFileSync(cfg.ledgerPath, JSON.stringify({
                ts: new Date().toISOString(), session: String(agent.session?.id || '').slice(0, 8),
                todos: todos.length, completed: doneItems.length, rejected: (s.rejectedItems || []).length, hasVerify: verifyItems.length,
              }) + '\n')
            } catch { /* ignore */ }
          } catch { /* ignore */ }
          s.pendingArchive = false
          info(`behavior-guard: [P0] 压缩后重注入任务存档（初始 ${s.initial.length} 字）`)
          const msg = createMessage(parts.join('\n'), 'task-continuity')
          const messages = Array.isArray(decision?.messages) ? [...decision.messages, msg] : [msg]
          return { ...decision, messages }
        }
        // P1.5：todo 回灌（recitation）
        if (cfg.todoEchoEnabled && s.pendingTodoEcho && Array.isArray(s.lastTodos) && s.lastTodos.length > 0) {
          s.pendingTodoEcho = false
          const items = s.lastTodos.slice(0, cfg.maxEchoItems).map((t) => (t?.status === 'completed' ? '☑' : t?.status === 'in_progress' ? '◐' : '☐') + ' ' + String(t?.content ?? '').slice(0, 60))
          const more = s.lastTodos.length > cfg.maxEchoItems ? `\n（另有 ${s.lastTodos.length - cfg.maxEchoItems} 项）` : ''
          info(`behavior-guard: [P1.5] todo 回灌 ${s.lastTodos.length} 项`)
          const msg = createMessage('[harness 状态复述] 你当前的 todo 清单（以此为准，不要重新从头追问已确认的信息）：\n' + items.join('\n') + more, 'task-continuity')
          const messages = Array.isArray(decision?.messages) ? [...decision.messages, msg] : [msg]
          return { ...decision, messages }
        }
        // P1：todo 闹钟（无单 / 停滞）
        if ((s.turnTodoInjections || 0) < cfg.maxTodoInjectionsPerTurn && (s.sessionTodoInjections || 0) < cfg.maxTodoInjectionsPerSession) {
          let text = ''
          if (s.todoCalls === 0 && s.step >= cfg.noTodoStepThreshold && !s.remindedNoTodo) {
            text = cfg.messageNoTodo
            s.remindedNoTodo = true
          } else if (s.todoCalls > 0 && (s.sinceLastTodo || 0) >= cfg.staleStepThreshold) {
            text = cfg.messageStale
            s.sinceLastTodo = 0
          }
          if (text) {
            s.turnTodoInjections = (s.turnTodoInjections || 0) + 1
            s.sessionTodoInjections = (s.sessionTodoInjections || 0) + 1
            info(`behavior-guard: [P1] todo 闹钟注入 todoCalls=${s.todoCalls} step=${s.step}`)
            const msg = createMessage(text, 'task-continuity')
            const messages = Array.isArray(decision?.messages) ? [...decision.messages, msg] : [msg]
            return { ...decision, messages }
          }
        }
      }

      // ── P2 Planner 检查（首次 [VERIFY] 项，每会话 1 次，独立于审计预算）──
      if (cfg.plannerCheckEnabled && s.pendingPlannerCheck && s.plannerChecked !== true) {
        s.plannerChecked = true
        try {
          const pc = await runPlannerCheck(s)
          s.pendingPlannerCheck = null
          if (pc && pc.verdict === 'UNVERIFIABLE') {
            const itemsTxt = Array.isArray(pc.items) && pc.items.length ? pc.items.join('；') : '(见验收项)'
            info(`behavior-guard: [Planner] 验收项不可验证 — ${String(itemsTxt).slice(0, 60)}`)
            const msg = createMessage(
              '[harness 计划评审] 你的验收项里有不可验证的表述：' + itemsTxt +
              '。修正为可执行判据：' + String(pc.fix || '写出具体命令/文件/阈值') +
              '。请更新 todo 的 [VERIFY] 项后继续。',
              'behavior-guard'
            )
            const messages = Array.isArray(decision?.messages) ? [...decision.messages, msg] : [msg]
            return { ...decision, messages }
          }
        } catch { /* ignore */ }
      }
      // v3.3 共享每轮注入预算（audit 注入 + turn-guard steer 合计，防叠加刷屏）
      if (s.sharedInjections >= cfg.sharedMaxPerTurn) return decision

      // v3.2 P0：代验收结果（spawn 验收 wait 连续超时 → verify_agent.py 环境判定）
      if (s.pendingVerify) {
        const pv = s.pendingVerify
        s.pendingVerify = null
        s.auditing = true
        let text = null
        try {
          // 相对路径解析到 workspaceRoot（verify_agent.py 的 cwd 不一定是工作区）
          const absProduct = resolveSafePath(pv.product) || pv.product
          const res = await runVerifyAgent(absProduct, pv.criteria)
          if (res) {
            info(`audit-loop: 代验收结论 ${res.verdict} — ${String(res.reason).slice(0, 80)}`)
            text = `[harness 代验收] 子智能体验收等待超时，系统已直接执行环境级验收（verify_agent.py，无历史、temperature=0）。\n产物：${pv.product}\n结论：${res.verdict}\n理由：${res.reason || '(无)'}\n${res.verdict === 'PASS' ? '验收通过——基于此事实收尾或继续后续步骤。' : res.verdict === 'FAIL' ? '验收未通过——请先修正产物，修正后再次触发独立验收。' : '无法判定——请补充产物证据后重新验收。'}`
          }
        } finally { s.auditing = false }
        if (text) {
          s.turnInjections += 1
          sessionInjections += 1
          const msg = createMessage(text, 'audit-loop')
          const messages = Array.isArray(decision?.messages) ? [...decision.messages, msg] : [msg]
          return { ...decision, messages }
        }
        return decision
      }

      // v3.1 D1/D2 确定性信号（每步检查，不等审计窗口）
      if (s.pendingInject) {
        const text = s.pendingInject
        s.pendingInject = null
        s.trail = [] // 修正后重新观察
        s.turnInjections += 1
        sessionInjections += 1
        const msg = createMessage(text, 'audit-loop')
        const messages = Array.isArray(decision?.messages) ? [...decision.messages, msg] : [msg]
        return { ...decision, messages }
      }
      if (s.pendingCorrector) {
        s.pendingCorrector = false
        if (s.turnInjections < cfg.maxInjectionsPerTurn && sessionInjections < cfg.maxInjectionsPerSession) {
          s.auditing = true
          let text = null
          try {
            const pkg = await runCorrector(s)
            if (pkg) {
              if (cfg.executorEnabled && pkg.action === 'retry_with') {
                const exec = executeReadOnly(pkg)
                if (exec) text = formatExecutorResult(pkg, exec)
              }
              if (!text) text = formatCorrection(pkg)
            }
          } finally { s.auditing = false }
          if (text) {
            s.turnInjections += 1
            sessionInjections += 1
            s.sharedInjections += 1
            s.trail = []
            const msg = createMessage(text, 'audit-loop')
            const messages = Array.isArray(decision?.messages) ? [...decision.messages, msg] : [msg]
            return { ...decision, messages }
          }
        }
        return decision
      }

      // 审计触发门控（2026-11-17 D5，SAG 原则 gated critique）：
      //   "precision intervention > constant supervision"——SAG（SKKU/Soongsil 2026-10）
      //   算力 -66% / 成功率 3 倍。固定周期（每 N 步）与真实风险无关，改为风险信号门控：
      //   (a) 轨迹中 FAIL/UNPRODUCTIVE ≥2（D2 已确定性覆盖，此处置门控开启）
      //   (b) 无进展：连续 ≥ noProgressSteps 步无 write 且无 todo 更新（漂移高危）
      //   (c) 本轮 present 已调用（交付前 = 风险最高点，与 D4 合流）
      //   (d) 刚经历压缩（状态重建高危期；由 s.justCompacted 标记，处理一次即清）
      //   确定性信号（D1/D2/D3）仍然每步零成本检查——那部分不变。
      const badCount = s.trail.filter((x) => x.kind === 'call' && (x.status === 'FAIL' || x.status === 'UNPRODUCTIVE')).length
      // MTP 信心信号：读 llama-server 日志尾部最后一条 draft acceptance（零额外推理）
      const specAcc = cfg.specSignalEnabled ? readSpecAcceptance(cfg.specLogPath) : null
      s.specAcceptance = specAcc
      let gateReason = ''
      if (badCount >= 2) gateReason = 'repeated-failure'
      else if (specAcc !== null && specAcc < cfg.specAcceptanceMin) gateReason = 'low-draft-acceptance'
      else if ((s.noProgressSteps || 0) >= (cfg.noProgressSteps || 6)) gateReason = 'no-progress'
      else if (s.presentCalled === true) gateReason = 'pre-delivery'
      else if (s.justCompacted === true) gateReason = 'post-compaction'
      if (!gateReason) return decision
      if (s.turnInjections >= cfg.maxInjectionsPerTurn) return decision
      if (sessionInjections >= cfg.maxInjectionsPerSession) return decision
      if (!s.trail.length) return decision
      s.justCompacted = false
      info(`audit-loop: [D5] 审计门控触发（${gateReason}）step=${s.step}`)

      // ── 审计员自校准闭环（2026-11-17，文献驱动）──
      // 结算上一次干预（3 步后看失败信号是否消失 = 采纳/有效），写 feedback jsonl。
      try {
        if (s.auditEval && s.step - s.auditEval.step >= 3) {
          const badNow = s.trail.filter((x) => x.kind === 'call' && (x.status === 'FAIL' || x.status === 'UNPRODUCTIVE')).length
          appendFileSync(cfg.auditFeedbackPath, JSON.stringify({
            ...s.auditEval, badNow, effective: badNow === 0, stepNow: s.step,
          }) + '\n')
          s.auditEval = null
        }
      } catch { /* ignore */ }

      s.auditing = true
      let text = null
      try {
        const audit = await runAudit(s)
        // 弃权通道（AGNOST 原则：证据不足必须可输出"不可确定"，不得被迫给 OK/ISSUE）
        if (audit && audit.verdict === 'UNCERTAIN') {
          info(`audit-loop: 审计弃权（证据不足）— ${String(audit.reason || '').slice(0, 60)}`)
          s.auditing = false
          return decision
        }
        if (audit && audit.verdict === 'ISSUE') {
          info(`audit-loop: 审计发现问题 — ${String(audit.issue).slice(0, 80)}`)
          // v2：交给纠正器产出修正包；失败则降级到 v1 的 fix 文本
          const pkg = await runCorrector(s)
          if (pkg) {
            // v3：只读操作由插件确定性代执行（构造性消除传递损耗）
            if (cfg.executorEnabled && pkg.action === 'retry_with') {
              const exec = executeReadOnly(pkg)
              if (exec) text = formatExecutorResult(pkg, exec)
            }
            if (!text) {
              text = formatCorrection(pkg)
            }
          }
          if (!text) {
            text = `[harness 独立审计] 无历史的审计员审阅了你最近的工具轨迹，发现：${audit.issue}。修正指令：${audit.fix}。请立即执行修正，不要辩解或重复已失败的路径。`
          }
          // ── CritBank 经验检索（零 LLM 成本：关键词匹配，2026-11-17）──
          // U-Fold 的"检索式上下文"思路：不让全部教训常驻 AGENTS.md（4K 内放不下），
          // 而是在信号命中时按轨迹特征检索最相关的 1~2 条注入。
          try {
            const lessons = matchCritbank(s)
            if (lessons.length) text = (text || '') + '\n' + lessons.join('\n')
          } catch { /* ignore */ }
        }
      } finally {
        s.auditing = false
      }
      if (!text) return decision

      s.turnInjections += 1
      sessionInjections += 1
      s.sharedInjections += 1
      s.trail = [] // 修正后重新观察
      // 自校准：记录本次干预（3 步后结算有效性：注入后 3 步内无新失败 = 有效）
      try {
        s.auditEval = { ts: new Date().toISOString(), kind: 'audit', gate: gateReason, rubric: AUDIT_RUBRIC.version || '', step: s.step }
      } catch { /* ignore */ }

      const msg = createMessage(text, 'audit-loop')
      const messages = Array.isArray(decision?.messages) ? [...decision.messages, msg] : [msg]
      return { ...decision, messages }
    } catch (error) {
      warn(`audit-loop: pre-step 失败 ${String(error)}`)
      return decision
    }
  })
}
