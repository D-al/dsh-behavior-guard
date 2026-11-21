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
