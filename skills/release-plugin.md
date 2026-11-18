---
name: release-plugin
summary: 发布/更新 dsh 插件的完整流程（改代码 → 测试 → CHANGELOG → tag → push → pnpm update → 重启验证）
keywords: [发布插件, 发布新版本, release, changelog, pnpm update, 打 tag, 推送到 github]
---
# 发布 dsh 插件

## 0. 前置确认
- 改的是 `C:\Users\Ad\.dsh\profiles\desktop\node_modules\<插件>\index.mjs`（运行副本）
- 发布副本在 `D:\Brain\publish\<仓库名>\`（git 仓库，remote 指向 GitHub）

## 1. 改代码 + 语法检查
```bash
node --check "C:/Users/Ad/.dsh/profiles/desktop/node_modules/<插件>/index.mjs"
```

## 2. 跑测试（必须全过才发布）
```bash
cd D:/WorkBuddyWorkSpace/2026-10-13-20-41-43/bench
node test_turn_guard.mjs      # 26 项
node test_new_guards.mjs      # 32 项
python regression_check.py    # 29 项门禁
```

## 3. 同步到发布副本 + 版本号 + CHANGELOG
```bash
cp node_modules/<插件>/index.mjs D:/Brain/publish/<仓库>/index.mjs
# 改 package.json 的 version（语义化：修 bug +0.0.1，新功能 +0.1.0，破坏性 +1.0.0）
# CHANGELOG.md 顶部插入条目（含依据/数据/测试数）
```

## 4. 提交并推送
```bash
cd D:/Brain/publish/<仓库>
git add -A && git commit -m "vX.Y.Z (日期 时间): 一句话变更"
git tag "vX.Y.Z-YYYYMMDD-HHMM"
git push origin main --tags
```

## 5. 更新运行副本 + 重启
```powershell
Get-Process "DeepSeek Harness",llama-server -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
Start-Sleep 5
cd C:\Users\Ad\.dsh\profiles\desktop
node 'D:\Deepseek Harness\resources\runtime\pnpm\bin\pnpm.cjs' update <包名>
Start-ScheduledTask -TaskName RestartDsh
Start-Sleep 65
curl.exe -s --max-time 4 http://127.0.0.1:8081/health
```

## 6. 验证加载
```powershell
Get-Item 'D:\Brain\workspace\bench\_agent_harness_loaded.json' | % { $_.LastWriteTime }
```
探针时间必须是**本次重启时间**（不是旧的）。初次集成还要确认 `hits`（设置/命令注册）。

## 7. 记录
把版本/tag/测试数追加到 `D:/Brain/workspace/memory/YYYY-MM-DD.md`。

## 常见坑
- **pnpm 必须在 profile 目录跑**（`C:\Users\Ad\.dsh\profiles\desktop`），且用 `node <pnpm.cjs>`
- **探针旧值误判**：探针文件时间戳要看是否等于本次重启时刻
- **双挂载**：bundle 插件不要同时在 preset 里显式挂载（会成对注入）
- **bundles 列表**要用**包名**（package.json 的 name），不是仓库名
