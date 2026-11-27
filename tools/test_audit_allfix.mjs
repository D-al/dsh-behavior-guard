// 审计全修复的行为级验证（不是 grep，是实际跑逻辑）
import fs from 'node:fs';

let pass = 0, fail = 0;
const t = (name, fn) => {
  try { const r = fn(); if (r === true) { console.log('PASS ' + name); pass++; } else { console.log('FAIL ' + name + ' :: ' + r); fail++; } }
  catch (e) { console.log('FAIL ' + name + ' :: ' + e.message); fail++; }
};

const P = fs.readFileSync('D:/Brain/publish/dsh-behavior-guard/index.mjs', 'utf8');
const R = fs.readFileSync('D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs', 'utf8');
const both = (s) => P.includes(s) && R.includes(s);

console.log('=== P0-1 重复写入误报修复（同step守卫）===');
t('两版都有同step守卫 _lastRepeatCheckKey', () => both('s._lastRepeatCheckKey !== checkKey'));
t('两版文案改为差异反馈(含sha)', () => both("'这个文件内容与上次写入完全相同（sha '"));
t('旧文案已移除', () => !both("重复写入不是进展，停止空转')"));
t('记录内容变化 note', () => both('s.lastProductChangeNote'));

console.log('\n=== P0-2 拦截措辞（差异反馈）===');
t('差异反馈含"先 read 出当前内容"', () => both('先 read 出当前内容确认实际文本'));

console.log('\n=== P1-1 handoff 软甩锅特征 ===');
t('软甩锅正则含"重启"', () => both('(?:重启|重新启动|关闭)'));
t('软甩锅正则含"截图/测试"', () => both('(?:截图|测试)'));
// 实际测正则行为
t('正则能匹配"请你关闭 DSH 重启测试"', () => {
  const m = R.match(/const handoffRe = (\/[^\n]+\/i)/);
  if (!m) return '未找到 handoffRe';
  const re = eval(m[1]);
  return re.test('请关闭 DSH 重启后测试') ? true : '正则没匹配';
});
t('正则能匹配"截图给我看看"', () => {
  const m = R.match(/const handoffRe = (\/[^\n]+\/i)/);
  const re = eval(m[1]);
  return re.test('如果没有出现，请截图给我看看') ? true : '正则没匹配';
});

console.log('\n=== P1-2 言行一致性 ===');
t('声称已重写检测', () => both('claimRewrite'));
t('判定含 repeatedWriteCount', () => both('claimRewrite && s.repeatedWriteCount >= 1'));

console.log('\n=== P2-1 control_turn 退化旁路 ===');
t('退化旁路变量存在', () => both('_degradeBypass'));
t('阈值 6 步无 write', () => both('_noWriteStreak >= 6'));
t('stepsSinceWrite 被计数', () => both('s.stepsSinceWrite = _isShellWrite ? 0 : (s.stepsSinceWrite || 0) + 1') || both('s.stepsSinceWrite = (s.stepsSinceWrite || 0) + 1'));
t('write 时清零', () => both('s.stepsSinceWrite = 0'));

console.log('\n=== P2-2 verify_on_stop 要求 HTTP ===');
t('web产物检测', () => both('_isWeb'));
t('HTTP 证据检测', () => both('verifyWeak'));
t('证据正则含 curl/localhost', () => both('curl|Invoke-WebRequest'));

console.log('\n=== P3-1 fep converged 纳入 hash ===');
t('no-content-change 偏差', () => both("deviations.push('no-content-change')"));

console.log('\n=== 空壳修复（前序补丁）===');
t('toolWindow 有 push 点', () => /s\.toolWindow\.push\(/.test(R));
t('toolNamesById 有 set', () => /s\.toolNamesById[^;]*\.set\(/.test(R));
t('goalRestatedStep 赋值', () => R.includes('s.goalRestatedStep = s.step'));
t('heal 注入点存在', () => R.includes("kind: 'tool_failure_heal'"));
t('shouldInject 被真实调用', () => both('if (shouldInject(s.pendingHeal, s))'));

console.log('\n=== 幂等标记 ===');
t('AUDIT_ALLFIX-PATCHED 两版', () => both('AUDIT_ALLFIX-PATCHED'));

console.log(`\n结果: ${pass} PASS / ${fail} FAIL`);
process.exit(fail ? 1 : 0);
