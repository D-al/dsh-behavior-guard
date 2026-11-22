/** 反模式匹配检测器单测：真阳/阴性/时机门槛 */
import assert from 'node:assert/strict'
import { detectPatternLock } from './s6_pattern_guard.mjs'
let pass = 0
function check(label, ok) { assert.ok(ok, label); pass++; console.log('PASS', label) }

const W = 12
const locked = Array(W).fill('read')
const diverse = ['read','glob','pwsh','grep','edit','write','read','glob','pwsh','grep','edit','write']

check('窗口不足不判', !detectPatternLock(Array(5).fill('read'), 20).hit)
check('锁定+时机够→命中', detectPatternLock(locked, 10).hit)
check('锁定但刚重述目标→不判(时机门槛)', !detectPatternLock(locked, 2).hit)
check('多样工具不判', !detectPatternLock(diverse, 20).hit)
check('半锁定不判', !detectPatternLock([...Array(6).fill('read'), ...Array(6).fill('glob')], 20).hit)
const r = detectPatternLock(locked, 10)
check('trace字段完整(dominant/repetition/stepsSinceGoal)', r.dominant === 'read' && r.repetition === 1 && r.stepsSinceGoal === 10)
console.log(`\n${pass} PASS`)
