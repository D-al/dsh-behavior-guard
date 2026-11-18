---
name: session-debug
summary: 会话排障——从 dsh 的 zstd 会话文件里还原真实轨迹、定位失败点、复现问题
keywords: [会话排障, 会话分析, 复盘, 还原轨迹, session.v4, zstd, 会话记录, 审计会话]
---
# 会话排障

## 会话文件在哪
`C:\Users\Ad\.dsh\sessions\<工作区标识>\session-<uuid>\session.v4.jsonl.zstd`
- 用 zstandard 流式解压：`zstandard.ZstdDecompressor().stream_reader(open(f,'rb')).read()`
- 每行一个 JSON 事件，关键 type：`user/message`、`assistant/message`（含 content 的 text/tool-call）、`tool/result`、`todo/write`

## 标准分析脚本骨架
```python
import json, zstandard
f = r'...\session.v4.jsonl.zstd'
raw = zstandard.ZstdDecompressor().stream_reader(open(f, 'rb')).read().decode('utf-8')
rows = [json.loads(l) for l in raw.split('\n') if l.strip()]
step = 0
for r in rows:
    if r.get('type') == 'assistant/message':
        step += 1
        blocks = r['data']['message']['content']
        tools = [b.get('name') for b in blocks if b.get('type') == 'tool-call']
        text = ''.join(b.get('text', '') for b in blocks if b.get('type') == 'text')
        print(f'step{step} tools={tools} body={len(text)}')
```
- 统计：步数、工具分布、重复调用（同参）、注入条数（`[harness `）
- 找失败点：`tool/result` 里以 `Error:` / `[stderr]` 开头的

## 判断"行为是否退化"的四个信号
1. 同一工具同参数 ≥3 次（重复探测）
2. 正文 ≥20 行代码但没有 write 调用（贴代码当交付）
3. 连续多步 todo 完全不变（空转）
4. 压缩后立即重述任务/重问（状态丢失）

## 复盘输出
- 给用户：**步骤数、耗时、失败次数、关键转折点**（哪一步开始跑偏、为什么）
- 不要贴原始 JSON；只给结论 + 3~5 条证据（step 号 + 一句话）
