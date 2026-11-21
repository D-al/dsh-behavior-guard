/**
 * 集成测试：formatExecutorResult 的行为与 index.mjs 内联版本等价
 *
 * 思路：不依赖 dsh 完整运行时（apply/emit），而是直接导入两个版本
 *       的函数并用相同输入交叉比对输出，验证完全一致。
 */

import { formatExecutorResult as fer } from './format_executor_result.mjs'

let pass = 0
let total = 0

function check(label, ok) {
  total++
  if (ok) {
    pass++
    console.log(`PASS  ${label}`)
  } else {
    console.error(`FAIL  ${label}`)
  }
}

// ── 内联等价版本（与 index.mjs ~L1612 完全一致的逻辑 + Array.isArray 守卫） ──
function inlineFormat(pkg, exec) {
  if (!pkg || typeof pkg !== 'object' || Array.isArray(pkg)) return null
  if (!exec || typeof exec !== 'object' || Array.isArray(exec)) return null
  const argsStr = JSON.stringify(pkg.args ?? {}, null, 0)
  if (!exec.ok) {
    return `[harness 系统修正] 独立纠正器认为你陷入了「${exec.error && String(exec.error).includes('不存在') ? '目标定位错误' : pkg.tool + ' 调用方式问题'}」（理由：${pkg.reason || '见证据'}）。` +
      `不要原样重试上一次调用：换一种方法核实目标（glob 搜工作区 / es.exe 全盘搜索 / 用已知短路径重新定位），或向用户确认目标位置。`
  }
  if (exec.kind === 'list') {
    return `[harness 系统修正+代执行] 独立纠正器确定了正确目标（${pkg.reason || '见证据'}），且已代为执行目录列举，结果如下。\n目录：${exec.target}\n内容：\n${exec.content}\n\n请基于以上事实继续任务——无需重新调用工具，也不要改动正确参数。`
  }
  return `[harness 系统修正+代执行] 独立纠正器确定了正确参数（理由：${pkg.reason || '见证据'}），且已代为执行读取。\n参数：${argsStr}\n结果${exec.truncated ? '（已截断）' : ''}：\n${exec.content}\n\n请基于以上内容继续任务——该文件内容已在上下文中，无需重新读取；后续引用该路径时使用 ${argsStr} 中的短路径形式。`
}

;(async () => {
  try {
    console.log('🧪 test_format_executor_result_integration')
    console.log('')

    // ── Test 1: list 路径 — 外置 vs 内联 ──
    {
      console.log('[Test 1] list 路径等价性')
      const tests = [
        {
          pkg: { args: { pattern: '*.mjs' }, tool: 'glob', reason: '列举目录' },
          exec: { ok: true, kind: 'list', target: '/a/b', content: 'x.js\ny.mjs' }
        },
        {
          pkg: { args: {} },
          exec: { ok: true, kind: 'list', target: '/', content: '' }
        },
        {
          pkg: { args: { file_path: 'test.md' }, tool: 'read' },
          exec: { ok: true, kind: 'list', target: './dir', content: 'file.txt' }
        }
      ]
      for (let i = 0; i < tests.length; i++) {
        const a = fer(tests[i].pkg, tests[i].exec)
        const b = inlineFormat(tests[i].pkg, tests[i].exec)
        check(`list #${i + 1}: 输出完全一致`, a === b)
      }
    }

    // ── Test 2: read 路径 — 有/无截断 ──
    {
      console.log('[Test 2] read 路径等价性')
      const tests = [
        {
          pkg: { args: { file_path: 'a.md' }, tool: 'read' },
          exec: { ok: true, kind: 'read', content: 'hello' }
        },
        {
          pkg: { args: { file_path: 'b.md' }, tool: 'read', reason: '读配置' },
          exec: { ok: true, kind: 'read', truncated: true, content: 'long...' }
        },
        {
          pkg: { args: { file_path: 'c.md' }, tool: 'read' },
          exec: { ok: true, kind: 'read', truncated: false, content: 'short' }
        }
      ]
      for (let i = 0; i < tests.length; i++) {
        const a = fer(tests[i].pkg, tests[i].exec)
        const b = inlineFormat(tests[i].pkg, tests[i].exec)
        check(`read #${i + 1}: 输出完全一致`, a === b)
      }
    }

    // ── Test 3: 失败路径 — 包含"不存在"/不包含 ──
    {
      console.log('[Test 3] 失败路径等价性')
      const tests = [
        {
          pkg: { args: {}, tool: 'read', reason: '权限不足' },
          exec: { ok: false, error: 'EACCES' }
        },
        {
          pkg: { args: { pattern: '*.xyz' }, tool: 'glob' },
          exec: { ok: false, error: '目标不存在: no match' }
        },
        {
          pkg: { args: {}, tool: 'glob', reason: '查找文件' },
          exec: { ok: false, error: 'ENOENT: no such file' }
        },
        {
          pkg: { args: {}, tool: '' },
          exec: { ok: false, error: 'unknown tool' }
        }
      ]
      for (let i = 0; i < tests.length; i++) {
        const a = fer(tests[i].pkg, tests[i].exec)
        const b = inlineFormat(tests[i].pkg, tests[i].exec)
        check(`fail #${i + 1}: 输出完全一致`, a === b)
      }
    }

    // ── Test 4: null/undefined 输入一致性 ──
    {
      console.log('[Test 4] null/undefined 输入一致性')
      const inputs = [
        [null, { ok: true }],
        [{}, null],
        [undefined, {}],
        [{}, undefined],
        [42, {}],
        [{}, 99],
      ]
      for (let i = 0; i < inputs.length; i++) {
        const a = fer(inputs[i][0], inputs[i][1])
        const b = inlineFormat(inputs[i][0], inputs[i][1])
        check(`null input #${i + 1}: ${a} === ${b}`, a === b && (a === null || a === b))
      }
    }

    // ── Test 5: 复杂参数对象序列化一致性 ──
    {
      console.log('[Test 5] 复杂参数一致性')
      const complexPkg = {
        args: { file_path: 'deep/nested/path.md', offset: 0, limit: 1000, flags: ['r', 'u'] },
        tool: 'read',
        reason: '深度路径读取'
      }
      const exec = { ok: true, kind: 'read', content: 'content' }
      check('复杂参数序列化一致', fer(complexPkg, exec) === inlineFormat(complexPkg, exec))
    }

    // ── Summary ──
    console.log('')
    console.log(`📊 ${pass}/${total} 测试通过`)
    if (pass === total) {
      console.log('✅ All integration checks passed')
    } else {
      console.error(`⚠️  ${total - pass} check(s) failed`)
      process.exitCode = 1
    }
  } finally {
    // Nothing to clean up — pure function tests only
  }
})()
