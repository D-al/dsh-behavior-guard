# 最近会话工具调用失败：原因与频率（2026-11-22）

> 触发：用户问"最近它的会话调用工具出现失败的原因都有哪些，频率怎么样"
> 方法：扫描 11-15 之后所有会话的 `tool/result` 事件，**只认结构化 `isError=true` / `data.error`**，
> 不扫结果文本关键词（那会把"读到的文件内容里含 error"误判成失败——实测 219 个 Error 命中里绝大多数是误报）。

## 一、总量与频率

- 统计范围：11-15 之后的会话，共 **2,000+ 次工具调用**
- 真实失败：**54 次**
- **总失败率约 2.6%**，但**在上升**：

| 日期 | 失败/总调用 | 失败率 |
|---|---|---|
| 11-17 | 0/10 | 0% |
| 11-19 | 4/335 | 1.2% |
| 11-20 | 15/488 | 3.1% |
| 11-21 | 18/769 | 2.3% |
| **11-22** | **17/355** | **4.8%** ← 最高 |

## 二、按工具

| 工具 | 失败次数 | 占失败 |
|---|---|---|
| edit | 20 | 37% |
| read | 16 | 30% |
| pwsh | 8 | 15% |
| glob | 5 | 9% |
| grep | 2 | 4% |
| 其余（web_fetch / read_image / ask_user_question）| 3 | 5% |

## 三、按错误码（精确分类）

| 错误码 | 次数 | 含义 |
|---|---|---|
| `FS_EDIT_NOT_FOUND` | **18** | edit 的 `old_string` 在文件里找不到 → 内容锚点失配 |
| `FS_NOT_FOUND` | **16** | read 的文件路径不存在 → 路径臆想或错字 |
| `SUBPROCESS_SPAWN_NOT_FOUND` | 6 | pwsh 要执行的命令/程序不存在 |
| `SEARCH_FAILED` | 6（glob 5 + grep 1）| 搜索路径或模式失败 |
| `FS_NOT_OBSERVED` | 1 | edit 观察状态失效 |
| `WEB_BLOCKED_URL` | 1 | web_fetch 访问 github.com 被非公网 IP 拦（禁用入口违规残留）|
| `IMAGE_UNSUPPORTED_FORMAT` | 1 | read_image 读 .html（格式不对）|
| `JOB_CONTROLLER_UNAVAILABLE` | 1 | 后台任务禁用后的违规残留 |
| `SEARCH_INVALID_PATTERN` | 1 | grep 正则语法错 |
| `ASK_CANCELLED` | 1 | 用户取消提问 |
| `ABORTED` | 1 | 工具调用被中断 |
| `INVALID_ARGS` | 1 | edit 的 old_string 为空 |

## 四、根因归纳（按重要性）

### 1. 文件系统类占 63%（34/54）——真正的大头
- **`FS_EDIT_NOT_FOUND` 18 次**：模型拿旧的/记错的内容当 `old_string` 去 edit。
  典型场景：文件已被改过、读的是缓存/摘要而非原文、空白或标点微差。
  → 这正是项目 `verify-on-edit` 守卫和 `tool-boundaries` 技能卡想解决的问题，但**失败率仍在上升**。
- **`FS_NOT_FOUND` 16 次**：模型**猜路径**而不是先 glob 确认。
  实例：`p\bench\ROADMAP.md`（不存在的相对路径）、`D:\publish\dsh-behavior-guard\STRATEGY.md`（少了 `Brain`）、
  `D:\Brain\workspace\node_modules\...`（错目录）。
  → 路径臆想可通过"先 glob 再 read"的纪律规避，但 AGENTS.md 已有此规则，模型仍犯。

### 2. 命令/搜索类占 24%（13/54）
- `SUBPROCESS_SPAWN_NOT_FOUND` 6 次：pwsh 里调用了不存在的命令
- `SEARCH_FAILED` 6 次：glob/grep 路径错或模式问题

### 3. 违规残留 + 其他占 13%（7/54）
- web_fetch / job controller 各 1 次：禁用入口的违规调用（已记在工具面审计）
- 取消/中断/参数错各 1-2 次

## 五、趋势解读（诚实标注）

失败率从 1.2% 升到 4.8%，但**不能简单归因为"模型变差"**：
- 11-22 样本只有 355 次调用且包含多轮受控实验（轻量任务反复 read/pwsh），分母小、波动大
- 11-20/21 的高失败率对应的是大量 edit 操作（改代码会话），edit 本身就是最容易失败的动词
- 单次失败率 ±1-2% 属正常波动

**能确定的**：失败类型高度集中（文件系统 63%），且 `FS_EDIT_NOT_FOUND` 是单一最大源（33%）。
**不能确定的**：失败率上升是否有统计显著性（需更多天、同任务类型对照）。

## 六、可操作的建议（未执行，待用户定）

1. **最高杠杆：edit 前强制 read**——`FS_EDIT_NOT_FOUND` 占 33%，若能在 edit 前用一次 read 确认 old_string，
   可消掉大头。项目已有 verify-on-edit（事后校验），缺的是**事前锚点确认**。
2. **路径臆想**：在 AGENTS.md 强化"不确定路径先 glob，禁止拼路径"——但规则已存在，效果有限；
   更可靠的是工具层返回 suggest（FS_NOT_FOUND 时列出相近文件）。
3. **不值得动**：web_fetch/job 违规残留（各 1 次，已接近清零）、取消/中断（正常行为）。

## 七、方法学纪律
- **失败判据只用结构化字段**（`isError`/`data.error`），绝不扫结果文本关键词——
  实测"Error"关键词命中 219 次，其中 200+ 是读到文件内容里恰好含 error，纯误报。
  这与项目"守卫正则只认执行动作、不扫内容"的铁律一致。
- 错误码从 `data.error` 的 dict 提取（注意是 Python repr 单引号，不是 JSON 双引号）。
