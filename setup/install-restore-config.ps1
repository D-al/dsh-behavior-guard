#Requires -Version 5.1
<#
.SYNOPSIS
  dsh-agent-harness 一键开箱安装/恢复脚本。

.DESCRIPTION
  把本仓库的配置、技能、工具、文档恢复到目标机器。设计目标：
  "另一台同配置电脑克隆本库 → 跑这一个脚本 → 全部修改到位"。

  恢复内容：
    1. 插件本体：pnpm add github:D-al/dsh-behavior-guard（或 -LocalRepo 用本地副本）
    2. AGENTS.md → dsh-data 根（dsh 每会话自动注入）
    3. 生产配置 → bench/（.env.llama / INI / template / critbank / rubrics / patch）
    4. skills/ → bench/skills/（10 个技能卡）
    5. tools/ → bench/（核心脚本）
    6. 文档 → bench/docs/

  安全设计：
    - 默认**不覆盖**已存在文件（除非 -Force）
    - 所有被覆盖文件先备份到 .bak-<时间戳>
    - -DryRun 只看会做什么，不实际改

.PARAMETER ProfileRoot
  dsh profile 根目录，默认 C:\Users\Ad\.dsh（可能是 junction 到 D:\Brain\dsh-data）

.PARAMETER BenchDir
  bench 工作目录，默认从 profile 内的 junction 解析，或显式指定

.PARAMETER Force
  覆盖已存在文件（仍会备份）

.PARAMETER DryRun
  只打印计划，不实际执行

.PARAMETER LocalRepo
  从本地仓库目录安装插件（离线场景），而非 GitHub

.EXAMPLE
  .\setup\install.ps1 -DryRun
  .\setup\install.ps1
  .\setup\install.ps1 -Force -BenchDir D:\Brain\workspace\bench
#>
param(
    [string]$ProfileRoot = 'C:\Users\Ad\.dsh',
    [string]$BenchDir = '',
    [switch]$Force,
    [switch]$DryRun,
    [string]$LocalRepo = ''
)

$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'

function Log([string]$msg) { Write-Host "[harness] $msg" }
function Would([string]$action) { if ($DryRun) { Write-Host "[DRYRUN] $action" -ForegroundColor Yellow } }

# 解析 bench 目录（优先显式参数，其次 junction，最后默认）
if (-not $BenchDir) {
    $candidate = Join-Path $ProfileRoot 'bench'
    if (Test-Path $candidate) { $BenchDir = $candidate }
    else { $BenchDir = 'D:\Brain\workspace\bench' }
}
Log "Repo   = $Repo"
Log "Profile= $ProfileRoot"
Log "Bench  = $BenchDir"
Log "Mode   = $(if ($DryRun) { 'DRYRUN' } elseif ($Force) { 'FORCE (backup first)' } else { 'SAFE (skip existing)' })"

# 通用复制函数（带备份）
function Copy-Asset {
    param([string]$Src, [string]$Dst, [string]$Label)
    if (-not (Test-Path $Src)) { Write-Warning "源缺失: $Src"; return }
    $dstDir = Split-Path -Parent $Dst
    if (-not (Test-Path $dstDir)) { Would "New-Item -ItemType Directory $dstDir"; if (-not $DryRun) { New-Item -ItemType Directory -Path $dstDir -Force | Out-Null } }
    if (Test-Path $Dst) {
        if (-not $Force) { Log "跳过（已存在）: $Label"; return }
        $bak = "$Dst.bak-$Stamp"
        Would "备份 $Dst → $bak"
        if (-not $DryRun) { Copy-Item -LiteralPath $Dst -Destination $bak -Force }
    }
    Would "复制 $Label → $Dst"
    if (-not $DryRun) { Copy-Item -LiteralPath $Src -Destination $Dst -Force }
    Log "写入: $Label"
}

# ── 0. 前置检查 ──
if (-not (Test-Path $ProfileRoot)) { throw "Profile 目录不存在: $ProfileRoot（先装 dsh 或改 -ProfileRoot）" }
if (-not (Test-Path (Join-Path $Repo 'index.mjs'))) { throw "不是有效的 harness 仓库: $Repo" }

# ── 1. AGENTS.md（最重要，dsh 每会话注入）──
Copy-Asset -Src (Join-Path $Repo 'config\AGENTS.md') -Dst (Join-Path $ProfileRoot 'AGENTS.md') -Label 'AGENTS.md'

# ── 2. 生产配置 → bench ──
$cfgMap = @{
    'env.llama'              = (Join-Path $ProfileRoot 'profiles\desktop\.env.llama')
    'llama-router-preset.ini'= (Join-Path $BenchDir 'llama-router-preset.ini')
    'chat_template_zh.jinja' = (Join-Path $BenchDir 'chat_template_zh.jinja')
    'critbank.json'          = (Join-Path $BenchDir 'critbank.json')
}
foreach ($name in $cfgMap.Keys) {
    Copy-Asset -Src (Join-Path $Repo "config\$name") -Dst $cfgMap[$name] -Label "config/$name"
}
# rubrics（4 个）
Get-ChildItem (Join-Path $Repo 'config\rubrics\*.json') | ForEach-Object {
    Copy-Asset -Src $_.FullName -Dst (Join-Path $BenchDir "rubrics\$($_.Name)") -Label "rubrics/$($_.Name)"
}
# patch
Copy-Asset -Src (Join-Path $Repo 'config\patches\autoparser-fix.patch') `
           -Dst (Join-Path $BenchDir 'patches\autoparser-fix.patch') -Label 'autoparser-fix.patch'

# ── 3. skills（10 个）──
Get-ChildItem (Join-Path $Repo 'skills\*.md') | ForEach-Object {
    Copy-Asset -Src $_.FullName -Dst (Join-Path $BenchDir "skills\$($_.Name)") -Label "skills/$($_.Name)"
}

# ── 4. tools（19 个核心脚本）──
Get-ChildItem (Join-Path $Repo 'tools\*') -File | ForEach-Object {
    Copy-Asset -Src $_.FullName -Dst (Join-Path $BenchDir $_.Name) -Label "tools/$($_.Name)"
}

# ── 5. docs（L2 参考文档）──
Get-ChildItem (Join-Path $Repo 'docs\*.md') | ForEach-Object {
    Copy-Asset -Src $_.FullName -Dst (Join-Path $BenchDir "docs\$($_.Name)") -Label "docs/$($_.Name)"
}

# ── 6. 插件本体 ──
if ($LocalRepo) {
    Log "本地插件安装: $LocalRepo（跳过 pnpm；手动 pnpm add 指向该目录）"
} else {
    $cmd = "node 'D:\Deepseek Harness\resources\runtime\primary-runtime\dependencies\pnpm\bin\pnpm.cjs' add github:D-al/dsh-behavior-guard"
    Would $cmd
    if (-not $DryRun) {
        Push-Location $ProfileRoot
        try { Invoke-Expression $cmd }
        finally { Pop-Location }
    }
}

# ── 7. 收尾提示 ──
Write-Host ''
Log '=== 安装完成（或 DRYRUN 结束）==='
if (-not $DryRun) {
    Write-Host '下一步：' -ForegroundColor Cyan
    Write-Host '  1) 确认 package.json 的 dsh.profile.bundles 含 dsh-agent-harness'
    Write-Host '  2) 重启 dsh: Stop-Process DeepSeek Harness → Start-ScheduledTask RestartDsh'
    Write-Host '  3) 验证探针: D:\Brain\workspace\bench\_agent_harness_loaded.json 时间戳应为本次重启'
    Write-Host '  4) 跑门禁: python bench/regression_check.py'
    Write-Host '  5) 若 autoparser 补丁需要: 按 config/patches/autoparser-fix.patch 重打后重编 b12244'
}
