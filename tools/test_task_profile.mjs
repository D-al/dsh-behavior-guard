import { taskProfile } from './task_profile.mjs'
let pass = 0, fail = 0
const check = (label, ok) => { if (ok) { pass++; console.log(`PASS  ${label}`) } else { fail++; console.log(`FAIL  ${label}`) } }

const readOnly = taskProfile({ writeCalls: 0, lastProduct: '' })
check('纯只读任务 → 不需 todo/验证/深检/交付闸门',
  !readOnly.needsTodo && !readOnly.needsVerify && !readOnly.needsDeepReview && !readOnly.needsTreeCheck)

const artifact = taskProfile({ writeCalls: 1, lastProduct: 'D:/x/file.md' })
check('有产物任务 → 全部守卫需要',
  artifact.needsTodo && artifact.needsVerify && artifact.needsDeepReview && artifact.needsTreeCheck)

const mutating = taskProfile({ writeCalls: 2, lastProduct: '' })
check('有写调用无产物 → 仍需验证（fail-closed）', mutating.needsVerify && mutating.kind === 'mutating')

const empty = taskProfile(null)
check('空 state → fail-closed（要求全部守卫，不因缺信号放松）',
  empty.kind === 'unknown' && empty.needsTodo && empty.needsVerify && empty.needsDeepReview)

console.log(`\n${pass}/${pass + fail} pass`)
process.exit(fail ? 1 : 0)
