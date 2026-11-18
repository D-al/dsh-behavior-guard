#Requires -Version 5.1
<#
.SYNOPSIS
  把本机运行副本的变更同步回 harness 仓库（Single Source of Truth 的反向流）。

.DESCRIPTION
  与 install.ps1 方向相反：
    install.ps1: 库 → 本机（新机器开箱）
    sync.ps1:    本机 → 库（日常改动回写）

  只同步"生产资产"（config/skills/tools/docs），不同步：
    - 临时实验脚本（_ 前缀）
    - 日志（memory/）
    - 测试结果（_*.json）
    - 备份（*.bak-*）

  同步后给出 git 命令提示（不自动 commit/push——需人工确认）。

.PARAMETER Repo
  仓库路径，默认本脚本上一级

.PARAMETER ProfileRoot / BenchDir
  同 install.ps1

.PARAMETER DryRun
  只打印差异，不实际复制

.PARAMETER Commit
  同步后自动 git add + commit（仍需手动 push）

.EXAMPLE
  .\setup\sync.ps1 -DryRun          # 看哪些文件有差异
  .\setup\sync.ps1                  # 同步
  .\setup\sync.ps1 -Commit          # 同步并提交
#>
param(
    [string]$Repo = '',
    [string]$ProfileRoot = 'C:\Users\Ad\.dsh',
    [string]$BenchDir = '',
    [switch]$DryRun,
    [switch]$Commit
)

$ErrorActionPreference = 'Stop'
if (-not $Repo) { $Repo = Split-Path -Parent $PSScriptRoot }
if (-not $BenchDir) {
    $candidate = Join-Path $ProfileRoot 'bench'
    $BenchDir = if (Test-Path $candidate) { $candidate } else { 'D:\Brain\workspace\bench' }
}
function Log([string]$m) { Write-Host "[sync] $m" }

$changed = 0
function Sync-One {
    param([string]$Src, [string]$DstRel, [string]$Label)
    if (-not (Test-Path $Src)) { return }
    $dst = Join-Path $Repo $DstRel
    $need = $false
    if (-not (Test-Path $dst)) { $need = $true }
    elseif ((Get-Item $Src).LastWriteTime -gt (Get-Item $dst).LastWriteTime) { $need = $true }
    elseif ((Get-FileHash $Src -Algorithm SHA256).Hash -ne (Get-FileHash $dst -Algorithm SHA256).Hash) { $need = $true }
    if (-not $need) { return }
    $script:changed++
    if ($DryRun) { Write-Host "[DRYRUN] 更新 $Label" -ForegroundColor Yellow }
    else {
        $dir = Split-Path -Parent $dst
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        Copy-Item -LiteralPath $Src -Destination $dst -Force
        Log "更新 $Label"
    }
}

# 1) AGENTS.md
Sync-One -Src (Join-Path $ProfileRoot 'AGENTS.md') -DstRel 'config\AGENTS.md' -Label 'config/AGENTS.md'

# 2) 配置
Sync-One -Src (Join-Path $ProfileRoot 'profiles\desktop\.env.llama') -DstRel 'config\env.llama' -Label 'config/env.llama'
Sync-One -Src (Join-Path $BenchDir 'llama-router-preset.ini') -DstRel 'config\llama-router-preset.ini' -Label 'config/llama-router-preset.ini'
Sync-One -Src (Join-Path $BenchDir 'chat_template_zh.jinja') -DstRel 'config\chat_template_zh.jinja' -Label 'config/chat_template_zh.jinja'
Sync-One -Src (Join-Path $BenchDir 'critbank.json') -DstRel 'config\critbank.json' -Label 'config/critbank.json'
Sync-One -Src (Join-Path $BenchDir 'patches\autoparser-fix.patch') -DstRel 'config\patches\autoparser-fix.patch' -Label 'config/patch'

# 3) rubrics
Get-ChildItem (Join-Path $BenchDir 'rubrics\*.json') -ErrorAction SilentlyContinue | ForEach-Object {
    Sync-One -Src $_.FullName -DstRel "config\rubrics\$($_.Name)" -Label "rubrics/$($_.Name)"
}

# 4) skills
Get-ChildItem (Join-Path $BenchDir 'skills\*.md') -ErrorAction SilentlyContinue | ForEach-Object {
    Sync-One -Src $_.FullName -DstRel "skills\$($_.Name)" -Label "skills/$($_.Name)"
}

# 5) tools（只同步库里已有的文件名，避免把实验脚本带进来）
Get-ChildItem (Join-Path $Repo 'tools\*') -File | ForEach-Object {
    $src = Join-Path $BenchDir $_.Name
    if (Test-Path $src) { Sync-One -Src $src -DstRel "tools\$($_.Name)" -Label "tools/$($_.Name)" }
}

# 6) docs（从 bench 根和 bench/docs 两处收）
$docRoot = Join-Path $BenchDir 'docs'
Get-ChildItem (Join-Path $Repo 'docs\*.md') -File | ForEach-Object {
    $name = $_.Name
    $src = Join-Path $docRoot $name
    if (-not (Test-Path $src)) { $src = Join-Path $BenchDir $name }
    if (Test-Path $src) { Sync-One -Src $src -DstRel "docs\$name" -Label "docs/$name" }
}

Log "变更文件数: $changed"
if ($changed -eq 0) { Write-Host '一切已是最新。' -ForegroundColor Green }

if ($Commit -and $changed -gt 0 -and -not $DryRun) {
    Push-Location $Repo
    try {
        git add -A
        git commit -m "sync: $(Get-Date -Format 'yyyy-MM-dd HH:mm') 本机配置/技能/工具回写" | Out-Null
        Log '已 commit。记得 git push。'
    } finally { Pop-Location }
} elseif ($changed -gt 0) {
    Write-Host 'Hint: use -Commit, or manually: cd repo; git add -A; git commit' -ForegroundColor Cyan
}
