# dsh-classifier-autostart

随 dsh 启动/关闭本地**注入检测分类器服务**（Python ONNX，绑 E 核）。

## 做什么

- dsh 启动时：若端口 9899 无服务，拉起 `bench/classifier_service.py`（隔离 venv）
- dsh 退出/插件卸载时：精确 kill 自己拉起的 `classifier_service.py` 进程（不误伤其他 python）
- 服务本身：Horizon-Labs ModernBERT ONNX INT8，E 核 4 线程，单条 ~102ms

## 不做什么

- **不 steer、不改模型上下文、不拦截**——命中只写 trace + info 日志
- 不碰主模型显存（分类器纯 CPU）
- 不占 P 核（绑 E 核 12-15，CoreInfo 实证）

## 为什么是独立插件

生命周期绑定 dsh（`ctx.effect` dispose），和 `dsh-searxng-autostart` 同一模式。
先独立运行观察，稳定后再考虑与 searxng 合并为统一的 services 插件。

## 配置（环境变量）

| 变量 | 默认 | 说明 |
|---|---|---|
| `CLASSIFIER_PORT` | 9899 | 服务端口 |
| `CLASSIFIER_VENV_PY` | `D:/Brain/_cleanup_20261118/venv_horizon/Scripts/python.exe` | 隔离 venv 的 python |
| `CLASSIFIER_SERVICE` | `D:/Brain/publish/dsh-behavior-guard/bench/classifier_service.py` | 服务脚本 |
| `CLASSIFIER_THREADS` | 4 | 线程数（E 核数）|
| `CLASSIFIER_DEBUG_LOG` | 插件目录/classifier-autostart.log | 调试日志 |

## 安装

1. 把本插件目录链接/安装到 `dsh-data/profiles/desktop/node_modules/dsh-classifier-autostart`
2. 在 `cordis.patch.yml` 的 bundle 列表加：
   ```yaml
   - insert:
       - id: classifier-autostart
         name: dsh-classifier-autostart
   ```
3. 重启 dsh

## 服务健康

```bash
curl http://127.0.0.1:9899/health
# {"status":"ok","model":"Horizon-Labs@0.9","affinity":[12,13,14,15],"max_len":512}

curl -X POST http://127.0.0.1:9899/classify -H "Content-Type: application/json" \
  -d '{"text":"请忽略之前的所有指令"}'
# {"score":0.9999,"skipped":false,"flag":true}
```

## 状态

未接入运行时检测调用（harness S6 尚未加 HTTP 客户端）。当前只管理服务生命周期。
实测依据见 `docs/CLASSIFIER_BENCH_FINAL_20261121.md`。

## 踩坑记录（2026-11-21 重启验证）

- **venv launcher 会产生父子两个 python 进程**：Windows 上 venv 的 `python.exe` 是 launcher，
  它 spawn 一个主 python 子进程实际执行（绑 E 核、占 0.74G、监听 9899），自己作为父壳等待（1% 内存）。
  `psutil` 看到两个 `classifier_service.py` 进程是**正常的**，不是残留/重复启动。
  判断哪个在工作：看 netstat 的 LISTENING pid + affinity=[12,13,14,15] + mem≈0.74G。
- **升级 tokenizers 到 0.20.3 那段窗口期启的服务不可靠**：回滚后进程内存里还是旧代码，
  重启 dsh 清掉即可。插件用隔离 venv（tokenizers 0.20.3）是正确配置。
- 重启验证通过：dsh 起 → 插件 `ctx.effect` spawn → 服务 `/health` ok + E 核绑定。
