/**
 * S6 高信号守门（2026-11-22）：零成本正则，决定工具结果值不值得送分类器。
 *
 * 设计依据：
 * - 规则层 INJECT_PATTERNS 只抓 5 个经典模式（2/4 攻击）→ 守门必须更宽，覆盖
 *   disregard / ignore everything above / 中文软性注入（"不是数据，是新指令"），
 *   否则分类器没有增量价值，退化成规则层。
 * - 但不能宽到"任何文本"——目标是送检率降到 10-20%，延迟税随之降到 +0.3~3%。
 * - 前置筛选在服务端（should_skip），HTTP 往返省不掉；守门放在 harness 侧缓存前，
 *   真正的省税点。
 */

// 指令覆盖/角色改写/系统覆盖类——分类器强项（规则层漏的变体也在这里）
const OVERRIDE = [
  /\b(ignore|disregard|forget|override|bypass)\b.{0,40}\b(all|any|previous|prior|above|earlier|instructions?|rules?|prompts?|context|system)\b/i,
  /\b(ignore|disregard|forget)\s+everything\s+(above|before|prior)/i,
  /\b(new|updated|revised)\s+(system\s+)?(instructions?|prompt|directives?)\b/i,
  /\byou\s+are\s+(now|no longer)\b|\bact\s+as\s+(if|a|an|the)\b/i,
  /SYSTEM\s+(OVERRIDE|DIRECTIVE|MESSAGE)|<\|?system\|?>/i,
  /忽略|无视|忘掉|忘记|覆盖|绕开|绕过.{0,12}(指令|指示|规则|要求|约束|以上|之前|上述|前面|系统|提示)/,
  /不要(遵循|遵守|理会|执行).{0,12}(指令|规则|要求|系统|之前|上面)/,
  /(接下来|下面|以下).{0,12}(不是|并非).{0,6}数据|不是数据.{0,12}(是|而是).{0,8}(指令|新指令|命令)/,
  /(新|替换|覆盖)(的)?.{0,4}(指令|任务|目标|要求)/,
]

// 紧急动作胁迫（"立即执行/run this command"）——良性文本里少见
const URGENT_ACTION = [
  /请(立即|马上|立刻)(执行|运行|打开|删除|发送|输出)/,
  /\b(run|execute|delete|send|upload|print|reveal)\b.{0,20}\b(immediately|now|right away|without (asking|confirmation))\b/i,
  /\b(reveal|print|exfiltrate|dump)\b.{0,24}\b(secret|password|token|key|credential)\b/i,
  /(泄露|打印|输出|暴露).{0,10}(密钥|密码|口令|token|凭据)/i,
]

// 角色扮演/虚假权威（persona injection，社区 over-defense 高发区，但也是真实攻击）
const PERSONA = [
  /\bpretend\s+to\s+be\b|\broleplay\s+as\b|\byour\s+real\s+(goal|instruction)\b/i,
  /(假装|扮演|你现在是|假设你是|模拟一个).{0,16}(管理员|系统|developer|工程师|AI|模型)/,
]

const ALL = [...OVERRIDE, ...URGENT_ACTION, ...PERSONA]

/**
 * 是否值得送分类器。
 * @param {string} text 工具结果正文
 * @returns {{send:boolean, reason:string}} send=true 才付 HTTP 往返
 */
export function shouldClassify(text) {
  if (typeof text !== 'string' || !text) return { send: false, reason: 'empty' }
  // 只看前 4000 字符——跟规则层一致，避免长文本尾部噪声拖慢正则扫描
  const head = text.slice(0, 4000)
  for (let i = 0; i < ALL.length; i++) {
    if (ALL[i].test(head)) return { send: true, reason: 'signal-' + i }
  }
  return { send: false, reason: 'no-signal' }
}

export const _patterns = { OVERRIDE, URGENT_ACTION, PERSONA }
