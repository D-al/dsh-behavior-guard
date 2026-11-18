---
name: debug-llama-server
summary: llama-server 起不来 / 卡死 / 变慢 / 显存异常的排查顺序
keywords: [llama-server, 卡死, 冻结, 显存不足, OOM, 起不来, 变慢, 端口占用]
---
# llama-server 排障

## 0. 先看三个数（永远先看观测，不猜）
```powershell
curl.exe -s --max-time 3 http://127.0.0.1:8081/health
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu,power.draw --format=csv,noheader
Get-ChildItem D:\Brain\dsh-data\profiles\desktop\node_modules\dsh-llama-server-autostart\llama-server-run.log | % { $_.Length; $_.LastWriteTime }
```
- 显存空闲 **<450 MiB → 必卡**（会 WDDM 换页到 1~2 t/s）
- 日志最后修改时间 > 3 分钟前且 /health 不通 → 可能已崩

## 1. 起不来
1. 看 `llama-server-run.log` 尾部 40 行，找 `error` / `failed to load` / `CUDA` / `out of memory`
2. 常见原因：显存不足（先把 dsh 停掉再启）、模型路径错、`--chat-template-file` 路径错
3. 端口占用：`netstat -ano | findstr :8081`

## 2. 卡死（/health 通但不生成）
1. `curl http://127.0.0.1:8081/slots`（路由模式必须 `?model=<已加载模型>`）
2. 两个进度值都 20 分钟不动 → 判死，重启计划任务
3. 看有没有 watchdog：`bench/freeze_watch.py` 应已由 Startup 拉起

## 3. 变慢
| 症状 | 检查 |
|---|---|
| decode < 20 t/s | 显存余量（<450 卡换页）、`--moe-cache-cpu-share`（必须 0）|
| prefill < 500 t/s | `--ubatch`（1536/2048）、CPU 是否被限速（沙箱派生进程会限速）|
| 每步固定 10s+ | `--ctx-checkpoints` 是否为 0（承重墙，必须 ≥2）|

## 4. 显存账（96K 下）
非专家权重 2326 / KV 780 / DeltaNet 状态 377（不可压）/ MoE cache 1022 / 主 compute ~550 /
MTP 600 / 视觉。调参只看 `nvidia-smi`，不看参数数字。

## 5. 重启（安全流程）
```powershell
Get-Process "DeepSeek Harness",llama-server -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
Start-Sleep 5
Start-ScheduledTask -TaskName RestartDsh
Start-Sleep 65
curl.exe -s --max-time 4 http://127.0.0.1:8081/health
```
需已登录用户会话（计划任务）。

## 6. 参数改动后必须确认生效
- 日志里搜 `args[upstream]` 行，看本次真实生效的参数
- `.env.llama` 覆盖 `llama-router-preset.ini`；`python bench/config_check.py` 检查两处一致性
