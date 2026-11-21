// index.mjs — dsh-classifier-autostart
//
// 随 DeepSeek Harness (dsh) 启动，在后台拉起本地「注入检测分类器服务」(Python ONNX)，
// dsh 退出/插件卸载时精确 kill 自己拉起的那个进程（只杀 classifier_service.py 的 python，
// 不误伤其他 python 进程）。
//
// 设计原则（照搬 dsh-searxng-autostart，已验证的生命周期模式）：
//   - 全程 try/catch，任何失败静默，绝不拖垮 dsh 启动；
//   - 不 import 任何框架包，只用 Node 内置 API；
//   - 服务本体在 publish/dsh-behavior-guard/bench/classifier_service.py（隔离 venv 运行）；
//   - 分类器只写 trace + info 日志，绝不 steer / 不改模型上下文（用户拍板）。
import { spawn, execFile } from 'node:child_process'
import net from 'node:net'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const LOG = process.env.CLASSIFIER_DEBUG_LOG || path.join(__dirname, 'classifier-autostart.log')
function dbg(msg) {
  try { fs.appendFileSync(LOG, new Date().toISOString() + ' ' + msg + '\n') } catch (e) { /* 忽略 */ }
}

const PORT = Number(process.env.CLASSIFIER_PORT || 9899)
// 隔离 venv（transformers 4.44 不认 modernbert，需在 venv 里用 tokenizers 0.20 + onnxruntime）
const VENV_PY = process.env.CLASSIFIER_VENV_PY || 'D:/Brain/_cleanup_20261118/venv_horizon/Scripts/python.exe'
const SERVICE = process.env.CLASSIFIER_SERVICE ||
  'D:/Brain/publish/dsh-behavior-guard/bench/classifier_service.py'
const THREADS = process.env.CLASSIFIER_THREADS || '4'

function probe(port) {
  return new Promise((resolve) => {
    const sock = net.connect(port, '127.0.0.1')
    let done = false
    const finish = (v) => { if (!done) { done = true; sock.destroy(); resolve(v) } }
    sock.setTimeout(800)
    sock.on('connect', () => finish(true))
    sock.on('error', () => finish(false))
    sock.on('timeout', () => finish(false))
  })
}

export const name = 'classifier-autostart'
// 不注入任何服务：本插件只管起停外部进程，通过固定端口与 harness 通信。
export const inject = []

export function apply(ctx, config) {
  dbg('apply called')
  try {
    ctx.effect(() => {
      let child = null
      const boot = async () => {
        try {
          const alive = await probe(PORT)
          if (alive) { dbg('classifier service already up on ' + PORT + ', skip'); return }
          if (!fs.existsSync(VENV_PY)) { dbg('venv python not found: ' + VENV_PY); return }
          if (!fs.existsSync(SERVICE)) { dbg('service script not found: ' + SERVICE); return }

          const logPath = path.join(__dirname, 'classifier-service.log')
          const logFd = fs.openSync(logPath, 'a')
          const spawnOpts = {
            detached: true,
            stdio: ['ignore', logFd, logFd],
            windowsHide: true,
          }
          // CREATE_NO_WINDOW：不弹控制台窗口
          spawnOpts.creationFlags = 0x08000000
          child = spawn(VENV_PY, ['-u', '-B', SERVICE, '--port', String(PORT), '--threads', THREADS], spawnOpts)
          fs.closeSync(logFd)
          child.on('error', (e) => dbg('spawn ERROR: ' + (e && e.message)))
          child.on('spawn', () => dbg('spawned OK pid=' + child.pid))
          child.unref()
          dbg('spawn issued pid=' + child.pid + ' port=' + PORT)
        } catch (e) { dbg('boot EXCEPTION: ' + (e && e.message)) }
      }
      boot()

      return () => {
        dbg('disposer called')
        try {
          // 按命令行精确匹配：只杀 classifier_service.py 的 python，不误伤其他 python 进程
          const ps = "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python' -and $_.CommandLine -match 'classifier_service.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
          execFile('powershell.exe', ['-NoProfile', '-Command', ps], { windowsHide: true }, () => {})
        } catch (e) { dbg('disposer EXCEPTION: ' + (e && e.message)) }
      }
    })
  } catch (e) { dbg('apply EXCEPTION: ' + (e && e.message)) }
}
