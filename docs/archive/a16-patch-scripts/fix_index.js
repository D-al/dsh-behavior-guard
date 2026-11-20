// Fix index.mjs using Node.js
import { readFileSync, writeFileSync } from 'fs';

const p = 'D:/Brain/publish/dsh-behavior-guard/index.mjs';
let src = readFileSync(p, 'utf-8');

if (!src.includes('const WRITE_CLAIM')) {
  console.error('ERROR: WRITE_CLAIM not found');
  process.exit(1);
}

const idx = src.indexOf('const WRITE_CLAIM\n');
const before = src.slice(0, idx);
const afterStart = src.slice(idx);
const linesAfter = afterStart.split('\n');

console.log('[DEBUG] Lines after WRITE_CLAIM:');
for (let i = 0; i < Math.min(6, linesAfter.length); i++) {
  console.log(`  ${i}: ${JSON.stringify(linesAfter[i].slice(0, 70))}`);
}

// Count broken lines to skip
let skip = 0;
for (let i = 0; i < linesAfter.length; i++) {
  if (i === 0 || 
      (linesAfter[i].includes('FUTURE') && !linesAfter[i].includes('PHRASES')) || 
      (linesAfter[i].includes('WILL') && !linesAfter[i].includes('PHRASES'))) {
    skip++;
    continue;
  }
  if (linesAfter[i].includes('PATH_RE')) break;
}

console.log(`[+] Will skip ${skip} broken lines`);

const newDefs = `const WRITE_CLAIM = /已(?:经)?(?:写入|保存|创建|生成|更新|落盘|建好|写好|放在)|保存到|写入到|写到了|生成到|written to|saved to|created file/i
// Future claim detection — catches "现在/接下来/下面 + 写/创建/实现 + X" patterns.
// These trigger L1 file-existence+mtime verification just like past-tense claims.
const FUTURE_PHRASES = /(?:现在|接下来|下面|马上|立即)(?:要|了|就|正在)?[：:]?\\s*(?:写|创建|生成|编写|实现|建立|产出|落盘|保存)/i
const ILL_PHRASES = /(?:我将|I'll)\\s+(?:要\\s+)?(?:写|创建|生成|编写|实现)/i
const WILL_PHRASES = /\\bwill\\s+(?:write|create|generate|build|implement|place|save)/i
function hasFutureClaim(line) {
  return FUTURE_PHRASES.test(line) || ILL_PHRASES.test(line) || WILL_PHRASES.test(line)
}`;

const restSrc = '\n'.join(linesAfter.slice(skip));
const newSrc = before + newDefs + '\n' + restSrc;

writeFileSync(p, newSrc, 'utf-8');
console.log(`[+] Wrote ${newSrc.length} bytes to index.mjs`);
console.log(`[+] CLAIM_PATTERNS present: ${newSrc.includes('CLAIM_PATTERNS')}`);
console.log(`[+] hasFutureClaim present: ${newSrc.includes('hasFutureClaim')}`);
