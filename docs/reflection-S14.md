# Reflection — S14 (2026-11-20)

## What happened

S14 目标是将 AGENTS.md 的编辑协议从裸 `read → edit → verify` 升级为"降低复现负担"版本，核心对策针对 RoPE 偏移导致的小模型逐字漂移问题。

### 执行过程

1. **读卡**：通过 `roadmap_check.py --next` 和 `--card S14` 确认任务内容。
2. **改 AGENTS.md**：在路由表后插入完整的「编辑协议」小节（约 50 行新增），同时更新路由表中"改代码"一行的描述。
3. **写测试**：创建 `tools/test_edit_protocol.py`，用正则从 AGENTS.md 提取并验证 6 个协议要素。结果 6/6 PASS。
4. **写文档**：`docs/EDIT_PROTOCOL_S14_20261120.md` 记录根因、协议内容、证据来源。
5. **写反思**：本文档。

### 踩过的坑与规避

- ✅ 没有反复 read/grep 同一文件——读完一次后立即动手 edit。
- ✅ 没有写补丁脚本不应用——直接 edit/write 落盘。
- ✅ 使用 `D:/Python/python.exe` 绝对路径而非 pwsh wrapper，避免 ENOENT/ParserError。
- ✅ 没有在回复中承诺将来时动作——每一步都是实际工具调用+落盘。

## What worked well

- **开工前建 todo**：收到 harness 提醒后立即建清单，按顺序推进无遗漏。
- **学术调研落地**：RoPE 偏移 + Diff-XYZ 文献结论转化为具体可执行的协议规则（文件大小阈值、锚点规则、doctor 模式）。
- **test 用 re 提取而非复制**：验证脚本从权威源（AGENTS.md）动态提取关键词匹配，避免了文本复制导致的漂移。

## What could be improved

- **AGENTS.md 行数增长**：原 ~105 行现在约 155 行。后续考虑是否将协议细节移到独立引用文件（如 `config/edit_protocol.md`），主文件只保留引用链接。
- **验证覆盖度**：当前 test 只做关键词存在性检查，未验证语义正确性（例如锚点规则是否自洽、策略矩阵是否有冲突）。下一步可增加结构化解析。

## Evidence chain

| 步骤 | 证据 |
|---|---|
| 读卡 | `roadmap_check.py --next` → S14; `--claim S14` → CLAIMED |
| 改文件 | `edit` tool result: "updated successfully" ×2 |
| 测协议 | `python tools/test_edit_protocol.py` → 6/6 PASS, rc=0 |
| 文档 | `docs/EDIT_PROTOCOL_S14_20261120.md` written |
| 反思 | 本文档 |

## Next steps (from roadmap)

跑完整验证链：`roadmap_check.py --verify S14` + `node --check index.mjs` + `py_compile` + git commit/push。
