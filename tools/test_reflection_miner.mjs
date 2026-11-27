import { hvrGate, mineCandidates, promotionGate, compactMetacognitive } from './reflection_miner.mjs'
let p = 0, f = 0
function t(name, cond) { if (cond) { p++; console.log('  PASS ' + name) } else { f++; console.log('  **FAIL** ' + name) } }

console.log('=== HVR 分流 ===')
t('无犹豫 → 不捕获（96%正确）', hvrGate('我直接读取文件内容并完成修改。').shouldCapture === false)
t('英文无犹豫 → 不捕获', hvrGate('I will read the file and apply the fix.').shouldCapture === false)
t('中文犹豫 → 捕获', hvrGate('等等，让我重新想一下这个路径。').shouldCapture === true)
t('英文犹豫 → 捕获', hvrGate('Wait, actually I was wrong about the path.').shouldCapture === true)
t('犹豫+验证 → 高置信', hvrGate('等等，路径可能不对，让我检查一下 glob 结果确认。').confidence >= 0.8)
t('犹豫无验证 → 低置信', hvrGate('等等，好像有问题。').confidence < 0.8)
t('空文本 → 不捕获', hvrGate('').shouldCapture === false)

console.log('=== 候选抽取 ===')
const real1 = '我意识到之前尝试从GitHub获取信息失败了，所以我应该直接在本地工作区构建这个项目。'
const c1 = mineCandidates(real1, { sid: 's1', step: 3 })
t('真实句子能抽出候选', c1.length > 0)
t('候选带来源锚点', c1.length > 0 && c1[0].source === 's1' && c1[0].step === 3)
t('候选默认 candidate+unverified', c1.length > 0 && c1[0].status === 'candidate' && c1[0].verified === false)
t('候选保留原文(raw)', c1.length > 0 && c1[0].raw.includes('GitHub'))
const real2 = '我发现PowerShell脚本中的三元运算符语法有误，应该改成 if/else 语法。'
const c2 = mineCandidates(real2, { sid: 's2', step: 5 })
t('第二类真实句能抽出', c2.length > 0)
t('无犹豫不抽取', mineCandidates('好的，我完成了任务。', {}).length === 0)

console.log('=== 三闸门 ===')
const mk = (pk, sid, verified, ts) => ({ patternKey: pk, signal: pk, source: sid, verified, status: 'candidate', created_at: ts })
const hist = [mk('路径', 's1', true, Date.now()-1000), mk('路径', 's2', true, Date.now()-2000)]
t('满足3次+跨2任务+已验证 → promote', promotionGate([mk('路径','s3',true,Date.now())], hist).promote.length === 1)
t('只有1次 → hold', promotionGate([mk('语法','s3',true,Date.now())], hist).hold.length === 1)
t('单任务重复 → hold', promotionGate([mk('路径','s1',true,Date.now())], [mk('路径','s1',true,Date.now()-1000), mk('路径','s1',true,Date.now()-2000)]).hold.length === 1)
t('未验证 → hold', promotionGate([mk('路径','s3',false,Date.now())], hist).hold[0].holdReason === 'unverified')
t('30天外不计入', promotionGate([mk('路径','s3',true,Date.now())], [mk('路径','s1',true,Date.now()-40*86400000), mk('路径','s2',true,Date.now()-40*86400000)]).hold.length === 1)

console.log('=== 紧凑元认知 ===')
const cc = compactMetacognitive(c1)
t('紧凑反馈非空', cc.length > 0)
t('紧凑反馈不含完整原文(防锚定)', !cc.includes('所以我应该在本地工作区构建这个项目'))
t('空候选 → 空串', compactMetacognitive([]) === '')

console.log('\n结果 ' + p + ' PASS / ' + f + ' FAIL')
process.exit(f ? 1 : 0)
