/**
 * buildTrailText — 纯函数版本
 *
 * 从 trail 数组构建紧凑的调用摘要文本，用于审计 prompt 注入。
 * 等价于 index.mjs 中 buildTrailText(s) 的内联逻辑。
 *
 * @param {Array<{kind?:string, step?:number, name?:string, args?:string, status?:string, ok?:boolean, result?:string}>} trail
 * @returns {string} 格式化后的 trail 文本（截断至最后 4000 字符）
 */
export function buildTrailText(trail) {
  const calls = trail.filter((x) => x.kind === 'call' || x.kind === 'todo')

  // v3.1：连续同名调用计数（重复探测信号，如 wait_agent ×3）
  const runByIndex = []
  let run = 1
  for (let i = 1; i <= calls.length; i++) {
    if (i < calls.length && calls[i].name === calls[i - 1].name) {
      run++
      runByIndex[i - 1] = run
    } else {
      if (run >= 3) runByIndex[i - 1] = run
      run = 1
      runByIndex[i - 1] = runByIndex[i - 1] || 1
    }
  }

  const lines = calls.map((x, i) => {
    const st = x.status || (x.ok === undefined ? '?' : (x.ok ? 'OK' : 'FAIL'))
    const rl = runByIndex[i] || 1
    const runMark = rl >= 3 ? ` [连续第${rl}次]` : ''
    return `step${x.step} ${x.name}(${(x.args || '').slice(0, 80)}) -> ${st}${runMark} | ${x.result || ''}`
  }).filter(Boolean)

  return lines.join('\n').slice(-4000)
}

// CLI 入口：当直接运行此脚本时，读取 stdin JSON 并输出结果
if (import.meta.url.startsWith('file:') && process.argv[1]?.endsWith('build_trail_text.mjs')) {
  let data = ''
  process.stdin.on('data', (chunk) => { data += chunk })
  process.stdin.on('end', () => {
    try {
      const trail = JSON.parse(data)
      console.log(buildTrailText(trail))
    } catch (e) {
      process.stderr.write(`ERROR: ${e.message}\n`)
      process.exit(1)
    }
  })
}
