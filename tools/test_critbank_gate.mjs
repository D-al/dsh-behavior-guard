// critbank 一致性门禁的 node wrapper（回归链统一入口）
import { spawnSync } from 'node:child_process'
const r = spawnSync('D:/Python/python.exe', ['tools/critbank_gate.py'], { encoding: 'utf8' })
const out = (r.stdout || '') + (r.stderr || '')
process.stdout.write(out)
process.exit(r.status === 0 ? 0 : 1)
