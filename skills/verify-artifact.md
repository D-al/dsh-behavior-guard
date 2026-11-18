---
name: verify-artifact
summary: 产物验收的完整清单（脚本/配置/文档/网页四类各自的可验证判据）
keywords: [验收, verify_agent, 产物验收, 交付验收, 独立验收, 验收标准]
---
# 产物验收

## 前提：做的人不能自己签字
- 自检只能把虚假完成率 12.7%→11.8%（IOV 896 任务实测），**必须外部验收**
- 两种验收方式（二选一）：
  1. `spawn_teammate` 验收者（只给路径 + 标准，不给工作过程）
  2. `python bench/verify_agent.py <产物> "<标准>"`（三态：PASS/FAIL/INCONCLUSIVE）

## 分类判据

### 脚本（.py / .ps1 / .sh）
- 语法：`python -m py_compile` / `bash -n`（plugin 已自动查 verify-on-edit）
- 依赖：顶层 import 都能 `find_spec`（plugin 深检已查）
- 入口：有 `if __name__ == "__main__"` 或明确函数签名
- 行为：**跑一遍最小用例**，比对预期输出（不要只看"没报错"）
- 无占位：`grep -n "TODO\|FIXME\|pass$"` 应为空

### 配置（.yml / .json / .ini / .env）
- 格式：yaml/json 能解析（cordis 的 `!!js` 扩展由 dsh 自己处理）
- 一致性：同一键在 .env 与 .ini 的取值一致（`bench/config_check.py`）
- 生效：改完必须重启 + 看日志里的 `args[upstream]` 确认参数真的传进去了
- 回滚：改前备份 `.bak-<原因>`

### 文档（.md）
- 结构：有标题层级、无空章节
- 无占位：无"待补充/占位/TODO"
- 引用：出现的绝对路径都存在（plugin 深检已查）
- 无重复段落（plugin 深检已查）

### 网页 / 前端
- 语法：`node --check`（JS）/ 浏览器控制台无错
- 功能：关键交互点一遍（不是"能打开"就算）
- 数据：页面上的数字与后端/文件内容对得上
- 响应式：窄屏不溢出（如相关）

## 交付
- 用 `present` 声明交付（会触发 D4 交付闸门 + Critic 评审 + 深检）
- 汇报里写：产物路径 + 验收方式 + 验收结论（三态）
