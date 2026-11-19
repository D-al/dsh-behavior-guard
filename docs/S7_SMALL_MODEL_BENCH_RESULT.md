# S7 CPU 小模型基准结果（2026-11-19，实测）

> 前置：路线图 S6（86M Prompt-Guard）/ M7（格式修复器）/ L5（Critic 预警）都假设"小模型放 CPU 内存"可行。
> 本轮下载 Qwen3-0.6B Q8_0（610MB）到 `D:/GGUF_Download/`，用独立 8090 实例（`-ngl 0 -t 6 -c 4096`）实测。

## 一、硬件与配置

- CPU: i7-12650H（10C/16T）；RAM 空闲 50.2G；主模型 35B 走 8081 不受影响（小模型纯 CPU）。
- 模型：Qwen3-0.6B-Q8_0.gguf（官方 Qwen3-0.6B-GGUF 仓库唯一 GGUF，Q8_0 610MB）。
- 服务：`llama-server -m ... --port 8090 -ngl 0 -t 6 -c 4096 --no-webui`（自编 b12244）。

## 二、实测数据（5 次取中位）

| 任务 | max_tokens=32~64 | max_tokens=512（思维链写完）| JSON 合法率 |
|---|---|---|---|
| 注入分类 | 931ms（**content 空**）| **4191ms** | 5/5 |
| 注入分类（命中样本）| 824ms（空）| **5340ms** | 5/5 |
| 格式修复 | 1798ms（空）| **6005ms** | 5/5 |
| main 入口判定 | 1381ms（空）| **2933ms** | 5/5 |

## 三、两个关键发现

### 1. Thinking 模型吃光 token（与 Critic S5-② 同源）
- `max_tokens=32~64` 时：`reasoning_content` 满、`content=''`、**JSON 0/5**。
- `enable_thinking:false` 参数在本引擎（b12244）**不生效**——reasoning 仍 5/5。
- `max_tokens=512` 时思维链（~175-249 completion tokens）写完，content 正常，**JSON 5/5**。
- **结论**：小模型若用 Qwen3 系列，必须给够 token 预算（≥512），或改用非 thinking 模型（Qwen2.5-0.5B-Instruct）。

### 2. CPU 延迟是硬伤（比文献边缘设备慢 10×）
- 调研里 0.5B 路由器在 8GB 边缘设备上是 **392ms**；本机实测 **4.2~6.0 秒**。
- 原因：思维链（175-249 token）在 CPU 上生成慢；若关思考会更快但参数不生效。
- **结论**：**Qwen3-0.6B 不适合当实时"周围神经"**（注入检测要求 <10ms，这里 4 秒）。
  S6 的 86M Prompt-Guard（类 BERT 单次分类）仍是对的方向，不能用 Qwen3-0.6B 替代。

## 四、对路线图的影响

- **S6**：规则层已交付（v2.21）；模型层必须用 **86M 级分类器**（Prompt-Guard），
  不能用 Qwen3-0.6B Q8_0。下载与实测 86M 模型列为后续。
- **M7（格式修复器）**：0.6B 格式修复 6 秒 vs 主模型 JSON 重试 10-45 秒——**仍有 2-7× 收益**，
  但必须先解决 thinking token 预算问题（给 ≥512），且要实测端到端。
- **L5（Critic 预警）**：单次 5 秒的预警层如果每 present 都跑，会显著拖慢交付——不推荐直接用 0.6B。

## 五、原始产物
- 基准脚本：`bench/small_model_bench.py`
- 结果 JSON：`bench/_small_model_bench.json`
- 服务日志：`bench/_tmp_small_model_server.log`

> 遵循知识资产沉淀规则：S7 的真实数字、thinking 陷阱、与文献的边缘设备差异都留档。
