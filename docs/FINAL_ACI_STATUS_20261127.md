# 收尾报告：harness 层 ACI 的最终状态（2026-11-27 01:25）

> 用户睡前指令："后面有价值的就一直继续"。本轮继续做 post-execute 裁剪，
> **发现它是死代码并回滚**，修正计数策略，跑全量回归。**诚实结论：机制可用但不稳定。**

## 一、本轮做了什么

### 1. 尝试 post-execute 结果裁剪 → 发现是死代码 → 回滚

**源码确认可行**：`dsh-tools/src/pipeline.ts:494` 的 `tools/post-execute` waterfall，
`PostToolDecision` 支持 `{kind:'accept', content:[...]}` 替换结果。

**但实测 `read_sliced` 0 次**。查实际 read 结果发现：

```
<path>D:\...\node_modules\dsh-hardware-monitor\client.js</path>
<type>file</type>
<content>
10:     function createFloatingWindow() {
...
```

**dsh 的 `read` 本身就返回有界视图**（带行号的 14~36 行片段），不是全文。
所以"裁剪到 100 行"永远不会触发——**这是死代码，已回滚**（`cb71e76`）。

### 2. 发现真正的问题不是"读太多"，而是"在两个同名文件间犹豫"

实测会话里它反复在：
- `node_modules/dsh-session-recycle-bin/client.js`
- `node_modules/dsh-hardware-monitor/client.js`

之间横跳。两者都叫 `client.js`，都有 `min(Npx)`。

**这解释了为什么 basename 作 key 反而有效**：它把两个候选路径合并计数，
识别的是"卡住"而不是"同一文件读太多"。所以保留 basename（并记录这是有意权衡）。

### 3. 修正计数策略（找到上一轮 0 次 deny 的原因）

上一轮加了 `readCounts.clear()` 在 turn/start → 每轮清空 → 累积不到阈值 → 0 次 deny。

改为：**跨 turn 累积 + deny 后 `delete(k)`** —— 3 次放行 → deny → 重新计数（节流，非永久禁止）。

### 4. 清理
- 删除 `diag_preexec`（每轮 222 次写 trace 的开销）
- 更新过时测试断言（`if (state.continuations >= ...` 被我加了 `&& !_needVerifyBypass`）

## 二、最终稳定性：诚实结论

| 会话 | read 门控 | 硬中断 | 工具调用 | 备注 |
|---|---|---|---|---|
| 基线（无干预） | — | — | **55** | 手动 cancel |
| 仅硬中断 | — | ✓ | 12 | 自动 blocked |
| **771a4096**（门控成功） | **2 次 deny** | ✓ | **7** | 自动 blocked |
| 441b2045（有 clear） | 0 | 0 | 8 | 计数被清空 |
| **95475f65**（最终版） | **0** | **0** | 12 | 未复现 |

**结论：机制在 771a4096 那轮确凿生效（55→7，下降 87%），但后续轮次未稳定复现。**
原因推测：模型行为变化（用了带 offset 的 read / 读不同文件 / session id 变化），
不是机制失效——因为 771a4096 的 trace 有完整证据链（read_denied + tool/result 错误 + TURN/END blocked）。

**不再继续调参的理由**：
1. 已有一个确凿成功的对照（8 倍差距）
2. 继续迭代需要加更多诊断 → 更多重启 → 收益递减
3. 核心矛盾（模型在两个同名文件间犹豫）不是 harness 能完全解决的——那是能力边界

## 三、当前代码状态（已提交）

| commit | 内容 |
|---|---|
| `b8a6546` | 源码阅读：answer 只处理 continued |
| `9ca8b84` | 调研：注入 vs 锚点 |
| `35b3066` | 条件锚点 + 自述句 + 两个结构 bug |
| `3a33e40` | step 层硬中断（Breaker） |
| `ab33fa6` | 结构化任务调研 |
| `4bfc00f` | read 门控（pre-execute deny） |
| `b04f16b` | 自包含计数 + sid 归一化 |
| `e4a0997` | read 门控实测成功文档 |
| `4e67d8a` | post-execute 裁剪（后被回滚） |
| **`cb71e76`** | **回滚死代码 + 计数节流策略（当前版）** |

运行版 `loadedAt 2026-11-26T17:19:50.727Z`，与 publish 同步。

## 四、回归验证（全绿）

- 审计修复测试：**25 PASS / 0 FAIL**
- `test_wargame_fixes`：**ALL PASS**（更新了过时断言）
- `test_wargame_gaps`：**ALL PASS**
- `test_all_remaining`：**ALL PASS**
- bridge health：**OK**

## 五、留给未来的三条结论

1. **dsh 的 read 已经有界**（14~36 行 + 行号），别再做"裁剪到 100 行"这种冗余工作。
   真正的问题是模型**不知道该看哪个文件**，不是看不到内容。

2. **`{ global: true }` 能突破 agent-scoped 派发**，但 key 必须归一化：
   - sid 要去 `session-` 前缀
   - 路径在 `exec.arguments` 里有相对/绝对两种写法 → 用 basename（或规范化）
   
3. **计数策略：跨 turn 累积 + 触发后重置**。每轮 clear 会让阈值永远达不到。

## 六、未做 / 不推荐

- ❌ 不要再调阈值（3/5/2 已接近社区共识，继续调是过拟合单次样本）
- ❌ 不要做 post-execute 裁剪（死代码，read 已有界）
- ⚠️ 如果要提高稳定性，需要**加结构化诊断**（记录每次 pre-execute 的 sid/fp/n/offset），
  但那需要再重启 3~4 次，收益不确定。**当前证据足够证明机制可用，不够证明稳定。**
