/**
 * turn-continuation-guard 的离线单测：不启动 dsh，mock 掉 ctx / agent 跑事件序列。
 * 用法: node bench/test_turn_guard.mjs
 */
import { apply } from '../index.mjs'
import { writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'

const results = []
function check(label, actual, expected) {
  const ok = actual === expected
  results.push({ label, ok, actual, expected })
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}  actual=${JSON.stringify(actual)} expected=${JSON.stringify(expected)}`)
}

function harness(config) {
  const handlers = new Map()
  const warnings = []
  const infos = []
  const ctx = {
    on(event, fn) {
      if (!handlers.has(event)) handlers.set(event, [])
      handlers.get(event).push(fn)
    },
    logger: {
      info: (m) => infos.push(m),
      warn: (m) => warnings.push(m)
    }
  }
  apply(ctx, { probePath: null, ...config }) // 测试不写生产探针
  const emit = async (event, ...args) => {
    for (const fn of handlers.get(event) ?? []) await fn(...args)
  }
  const steered = []
  const agent = { session: { id: 's1' }, steer: (m) => steered.push(m) }
  return { emit, steered, agent, warnings, infos }
}

const textMsg = (...blocks) => ({ type: 'assistant/message', data: { message: { content: blocks } } })
const text = (t) => ({ type: 'text', text: t })
const toolCall = () => ({ type: 'tool-call', name: 'pwsh', arguments: '{}' })

// ---- 场景 1：退化（本轮用过工具，最后只回「好」且无 tool_calls）→ 必须 steer 一次
{
  const h = harness({})
  await h.emit('session/event', { id: 's1' }, { type: 'turn/start', data: { turn: 7 } })
  await h.emit('session/event', { id: 's1' }, { type: 'tool/call', data: {} })
  await h.emit('session/event', { id: 's1' }, textMsg(text('好')))
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 7 })
  check('退化 → steer 次数', h.steered.length, 1)
  check('steer 消息 role', h.steered[0]?.role, 'user')
  check('steer 消息 source', h.steered[0]?.source?.kind, 'behavior-guard')
  check('steer 消息有 id', typeof h.steered[0]?.id, 'string')
}

// ---- 场景 2：同一轮再次 turn-stopping → 限次，不再 steer
{
  const h = harness({ maxContinuationsPerTurn: 1 })
  await h.emit('session/event', { id: 's1' }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: 's1' }, { type: 'tool/call', data: {} })
  await h.emit('session/event', { id: 's1' }, textMsg(text('好')))
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 1 })
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 1 })
  check('同轮第二次 → 仍只 steer 一次', h.steered.length, 1)
}

// ---- 场景 3：正常长答复 → 不 steer
{
  const h = harness({})
  await h.emit('session/event', { id: 's1' }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: 's1' }, { type: 'tool/call', data: {} })
  await h.emit('session/event', { id: 's1' }, textMsg(text('文件已生成，内容是 6 行 VBS，路径已确认。')))
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 1 })
  check('正常答复 → 不 steer', h.steered.length, 0)
}

// ---- 场景 4：闲聊（本轮从未调用工具），回「好」→ 不 steer
{
  const h = harness({})
  await h.emit('session/event', { id: 's1' }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: 's1' }, textMsg(text('好')))
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 1 })
  check('闲聊短答复 → 不 steer', h.steered.length, 0)
}

// ---- 场景 5：最后一条 assistant 带了 tool_calls → 不 steer
{
  const h = harness({})
  await h.emit('session/event', { id: 's1' }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: 's1' }, { type: 'tool/call', data: {} })
  await h.emit('session/event', { id: 's1' }, textMsg(text('好'), toolCall()))
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 1 })
  check('有 tool_calls → 不 steer', h.steered.length, 0)
}

// ---- 场景 6：新轮次重置计数，可以再次救
{
  const h = harness({ maxContinuationsPerTurn: 1 })
  await h.emit('session/event', { id: 's1' }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: 's1' }, { type: 'tool/call', data: {} })
  await h.emit('session/event', { id: 's1' }, textMsg(text('好')))
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 1 })
  await h.emit('session/event', { id: 's1' }, { type: 'turn/start', data: { turn: 2 } })
  await h.emit('session/event', { id: 's1' }, { type: 'tool/call', data: {} })
  await h.emit('session/event', { id: 's1' }, textMsg(text('好的')))
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 2 })
  check('新轮次重置 → 共 steer 两次', h.steered.length, 2)
}

// ---- 场景 7：畸形输入不得抛异常（插件失败会结束轮次）
{
  const h = harness({})
  let threw = false
  try {
    await h.emit('session/event', undefined, undefined)
    await h.emit('session/event', { id: 's1' }, { type: 'assistant/message', data: { message: { content: null } } })
    await h.emit('session/event', { id: 's1' }, { type: 'turn/start', data: { turn: 1 } })
    await h.emit('session/event', { id: 's1' }, { type: 'tool/call' })
    await h.emit('session/event', { id: 's1' }, { type: 'assistant/message', data: {} })
    await h.emit('agent/turn-stopping', {})
    await h.emit('agent/turn-stopping', { agent: { session: undefined } })
  } catch {
    threw = true
  }
  check('畸形输入 → 不抛异常', threw, false)
}

// ---- 场景 8：会话总量上限生效
{
  const h = harness({ maxContinuationsPerTurn: 5, maxContinuationsPerSession: 2 })
  for (let turn = 1; turn <= 4; turn += 1) {
    await h.emit('session/event', { id: 's1' }, { type: 'turn/start', data: { turn } })
    await h.emit('session/event', { id: 's1' }, { type: 'tool/call', data: {} })
    await h.emit('session/event', { id: 's1' }, textMsg(text('好')))
    await h.emit('agent/turn-stopping', { agent: h.agent, turn })
  }
  check('会话上限 2 → 只 steer 两次', h.steered.length, 2)
}

// ---- 场景 9：L1 —— 声称「已写入 X」但文件不存在 → 必须 steer（本轮可以没用过工具）
{
  const h = harness({})
  await h.emit('session/event', { id: 's1' }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: 's1' }, textMsg(text('已完成，代码已写入 D:/__no_such_dir__/calc.py，可以直接运行。')))
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 1 })
  check('L1 声明不存在文件 → steer', h.steered.length, 1)
  check('L1 消息带上路径', h.steered[0]?.content?.[0]?.text?.includes('calc.py'), true)
  check('L1 消息说明不存在', h.steered[0]?.content?.[0]?.text?.includes('不存在'), true)
}

// ---- 场景 10：L1 反例 —— 文件真实存在 → 不 steer
{
  const real = path.join(tmpdir(), 'guard_real_' + Date.now() + '.py')
  writeFileSync(real, 'print(1)\n')
  const h = harness({})
  await h.emit('session/event', { id: 's1' }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: 's1' }, textMsg(text(`改好了，已写入 ${real}，可以运行。`)))
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 1 })
  check('L1 文件存在 → 不 steer', h.steered.length, 0)
}

// ---- 场景 11：L2 —— 本轮只有 read，正文贴 25 行代码、无写文件调用 → steer
{
  const code = '```python\n' + Array.from({ length: 24 }, (_, i) => `line_${i} = ${i}`).join('\n') + '\n```'
  const h = harness({})
  await h.emit('session/event', { id: 's1' }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: 's1' }, { type: 'tool/call', data: { name: 'read' } })
  await h.emit('session/event', { id: 's1' }, textMsg(text('这是实现：\n\n' + code + '\n\n完成。')))
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 1 })
  check('L2 贴大段代码且未写文件 → steer', h.steered.length, 1)
  check('L2 消息提到落盘', h.steered[0]?.content?.[0]?.text?.includes('write'), true)
}

// ---- 场景 12：L2 反例 —— 本轮调用过 write → 不 steer
{
  const code = '```python\n' + Array.from({ length: 24 }, (_, i) => `x_${i} = ${i}`).join('\n') + '\n```'
  const h = harness({})
  await h.emit('session/event', { id: 's1' }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: 's1' }, { type: 'tool/call', data: { name: 'write' } })
  // S13-compliant verify evidence: file_path with test_ prefix triggers verifyEvidence exact-match
  await h.emit('session/event', { id: 's1' }, { type: 'tool/call', data: { name: 'read', arguments: '{"file_path":"test_verify_output.txt"}' } })
  await h.emit('session/event', { id: 's1' }, textMsg(text('已写入 calc.py，内容如下：\n\n' + code)))
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 1 })
  check('L2 本轮调用过 write → 不 steer', h.steered.length, 0)
}

// ---- 场景 13：L2 反例 —— 纯闲聊贴代码（本轮没用过任何工具）→ 不 steer
{
  const code = '```python\n' + Array.from({ length: 30 }, (_, i) => `y_${i} = ${i}`).join('\n') + '\n```'
  const h = harness({})
  await h.emit('session/event', { id: 's1' }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: 's1' }, textMsg(text('给你看一段代码：\n\n' + code)))
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 1 })
  check('L2 闲聊贴代码 → 不 steer', h.steered.length, 0)
}

// ---- 场景 14：小代码块（<20 行）不触发 L2
{
  const code = '```python\n' + Array.from({ length: 5 }, (_, i) => `z_${i} = ${i}`).join('\n') + '\n```'
  const h = harness({})
  await h.emit('session/event', { id: 's1' }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: 's1' }, { type: 'tool/call', data: { name: 'read' } })
  await h.emit('session/event', { id: 's1' }, textMsg(text('这个函数是这样：\n\n' + code + '\n\n就这些。')))
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 1 })
  check('L2 小代码块 → 不 steer', h.steered.length, 0)
}

// ---- 场景 15：真实现场（Q4b 的 P2）—— 第 2 步把整份 linecount.py 贴正文、无 write
{
  const real = [
    '```python', 'import os', 'import sys', 'import argparse', '',
    'def count_lines(filepath):', '    with open(filepath) as f:',
    '        return sum(1 for _ in f)', '',
    'def main():', '    parser = argparse.ArgumentParser()',
    "    parser.add_argument('directory')", "    parser.add_argument('--ext')",
    '    args = parser.parse_args()', '    matches = []',
    '    for name in os.listdir(args.directory):',
    "        if name.endswith(args.ext):",
    '            matches.append((name, count_lines(name)))',
    '    matches.sort(key=lambda x: x[1], reverse=True)',
    '    print("filename,lines")',
    '    for n, c in matches:', '        print(f"{n},{c}")', '',
    "if __name__ == '__main__':", '    main()', '```'
  ].join('\n')
  const h = harness({})
  await h.emit('session/event', { id: 's1' }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: 's1' }, { type: 'tool/call', data: { name: 'read' } })
  await h.emit('session/event', { id: 's1' }, textMsg(text(real)))
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 1 })
  check('真实现场(Q4b P2) → steer', h.steered.length, 1)
}

// ---- 场景 16：L0 —— 空正文、无 tool_calls → steer（「想完不干」）
{
  const h = harness({})
  await h.emit('session/event', { id: 's1' }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: 's1' }, textMsg())
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 1 })
  check('L0 空正文无工具 → steer', h.steered.length, 1)
  check('L0 消息说明这一轮是空的', h.steered[0]?.content?.[0]?.text?.includes('空的'), true)
}

// ---- 场景 17：L0 真实现场（Q4@temp0.1 跑 P4 第 1 步）——
//      只产出 683 字思考、正文空、无 tool_calls、finish=stop；本轮此前没有任何工具调用
{
  const reasoning = { type: 'reasoning', text: '嗯，用户让我修复一个小型库存系统的bug。首先我应该运行测试看看具体的错误信息……接下来逐个检查每个源文件……' }
  const h = harness({})
  await h.emit('session/event', { id: 's1' }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: 's1' }, textMsg(reasoning))
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 1 })
  check('L0 真实现场(Q4@0.1 P4) → steer', h.steered.length, 1)
}

// ---- 场景 18：L0 反例 —— 空正文但带了 tool_calls（正常的多步调用）→ 不 steer
//      （已在场景 5 覆盖「正文+tool_calls」，这里专门测「纯 tool_calls、正文空」）
{
  const h = harness({})
  await h.emit('session/event', { id: 's1' }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: 's1' }, textMsg(toolCall()))
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 1 })
  check('L0 空正文但有 tool_calls → 不 steer', h.steered.length, 0)
}

// ---- 场景 19：L0 可关闭（blockEmptyFinish=false）→ 不 steer
{
  const h = harness({ blockEmptyFinish: false })
  await h.emit('session/event', { id: 's1' }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: 's1' }, textMsg())
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 1 })
  check('L0 关闭后 → 不 steer', h.steered.length, 0)
}

const failed = results.filter((r) => !r.ok)
console.log(`\n${results.length - failed.length}/${results.length} 通过`)
process.exit(failed.length === 0 ? 0 : 1)
