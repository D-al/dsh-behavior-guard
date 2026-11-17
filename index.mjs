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
import { writeFileSync, readFileSync, readdirSync, statSync, existsSync } from 'node:fs'
import path from 'node:path'
import { execFile } from 'node:child_process'

export const name = 'behavior-guard'

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
  probePath: '',
  // CritBank：结构化失效教训库（零 LLM 成本的检索式注入；U-Fold 检索式上下文思路）
  critbankPath: 'D:/Brain/workspace/bench/critbank.json'
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
        continuations: 0, totalContinuations: 0, last: undefined, sharedInjections: 0 }
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
        return
      }
      if (event.type === 'user/message' && event.data?.source?.kind === 'user') {
        const t = blocksText(event.data.content).trim()
        if (t && !t.startsWith('<system-reminder>')) s.initial = t.slice(0, 400)
        return
      }
      // v3.3 todo/write 观测：冗余更新检测（与上次 todos 内容完全一致 = 无意义调用）
      if (event.type === 'todo/write') {
        try {
          const todos = event.data?.todos
          const sig = JSON.stringify(todos)
          const arr = Array.isArray(todos) ? todos : []
          const done = arr.filter((x) => x && x.status === 'completed').length
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
          if (status === 'OK' && (c.name === 'write' || c.name === 'edit')) {
            try {
              const a = JSON.parse(c.fullArgs || c.args || '{}')
              if (a.file_path) s.lastProduct = String(a.file_path)
            } catch { /* ignore */ }
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

  const AUDIT_PROMPT = (task, trail) => `你是独立会话审计员，没有参与这段 agent 工作。只依据以下事实判断，不要猜测。

【任务】${task || '(未知)'}

【最近工具轨迹（状态三档：OK=有进展 / FAIL=报错 / UNPRODUCTIVE=超时或空结果无进展）】
${trail}

检查三类明确问题：
A. 重复失败或重复非生产：同一目标的 FAIL 或 UNPRODUCTIVE 结果出现 2 次以上。
B. 跑偏：出现了与任务明显无关的动作。
C. 重复探测无进展：同一工具带相同参数连续调用 3 次以上（轨迹标[连续第N次]）。

只输出 JSON（无其他文字）：
{"verdict":"OK"}
或
{"verdict":"ISSUE","issue":"一句话指出哪个 step 什么问题","fix":"一句话修正指令，直接命令下一步该做什么"}`

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

注意：args 必须是可直接调用的完整参数（严格 JSON 对象），不要省略号。
参数 schema 必须与真实工具一致（read: {file_path}; glob: {pattern}; pwsh: {command}），
禁止编造参数名或使用其他工具的参数。
路径约束：若目标在工作区 junction 覆盖范围内（p/ bench/ memory/ dsh/ wb/ llama/ gguf/ 任一前缀可达），
args 里的路径必须改写为短相对路径（如 memory/2026-11-16.md），禁止 70+ 字符的绝对路径——
主模型抄写长路径会逐字漂移（实测）。`

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
    return callLLM(AUDIT_PROMPT(s.initial, trail), 600, cfg.auditTimeoutMs)
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

      // ── D4 present-gate：present 声明交付但本轮无独立验收痕迹（verify-gated completion）──
      if (
        cfg.presentGateEnabled &&
        state.presentCalled === true &&
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
      let gateReason = ''
      if (badCount >= 2) gateReason = 'repeated-failure'
      else if ((s.noProgressSteps || 0) >= (cfg.noProgressSteps || 6)) gateReason = 'no-progress'
      else if (s.presentCalled === true) gateReason = 'pre-delivery'
      else if (s.justCompacted === true) gateReason = 'post-compaction'
      if (!gateReason) return decision
      if (s.turnInjections >= cfg.maxInjectionsPerTurn) return decision
      if (sessionInjections >= cfg.maxInjectionsPerSession) return decision
      if (!s.trail.length) return decision
      s.justCompacted = false
      info(`audit-loop: [D5] 审计门控触发（${gateReason}）step=${s.step}`)

      s.auditing = true
      let text = null
      try {
        const audit = await runAudit(s)
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

      const msg = createMessage(text, 'audit-loop')
      const messages = Array.isArray(decision?.messages) ? [...decision.messages, msg] : [msg]
      return { ...decision, messages }
    } catch (error) {
      warn(`audit-loop: pre-step 失败 ${String(error)}`)
      return decision
    }
  })
}
