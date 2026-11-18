#Requires -Version 5.1
<#
.SYNOPSIS
  创建 dsh 工作区所需的 junction 映射（一键开箱的最后一环）。

.DESCRIPTION
  新机器克隆 harness 库 + 跑 install.ps1 后，跑本脚本建立 7 个稳定 junction，
  使 AGENTS.md 里的短路径（bench/ memory/ p/ dsh/ llama/ gguf/ wb/）全部可达。

  设计要点：
    - p/ 指向 D:\Brain\workspace（稳定根，**无时间戳**）——这是 A1 可移植性改造的核心
    - 每个 junction 先检查再建，已存在且目标正确则跳过，目标错误则警告（不擅自删除）
    - -Force 才替换目标错误的 junction

.PARAMETER WorkspaceRoot
  dsh 工作区根，默认 C:\Users\Ad\Documents\deepseek-harness\default-workspace

.PARAMETER BrainRoot
  脑数据根，默认 D:\Brain

.PARAMETER Force
  目标错误时替换 junction

.PARAMETER DryRun
  只打印计划

.EXAMPLE
  .\setup\links.ps1 -DryRun
  .\setup\links.ps1 -Force
#>
param(
    [string]$WorkspaceRoot = 'C:\Users\Ad\Documents\deepseek-harness\default-workspace',
    [string]$BrainRoot = 'D:\Brain',
    [switch]$Force,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
function Log([string]$m) { Write-Host "[links] $m" }

# 7 个 junction 的映射（A1 改造后：p/ 指向稳定根）
$links = @(
    @{ Name = 'bench';  Target = Join-Path $BrainRoot 'workspace\bench' },
    @{ Name = 'memory'; Target = Join-Path $BrainRoot 'workspace\memory' },
    @{ Name = 'p';      Target = Join-Path $BrainRoot 'workspace' },        # 稳定根，无时间戳
    @{ Name = 'dsh';    Target = Join-Path $BrainRoot 'dsh-data' },
    @{ Name = 'gguf';   Target = 'D:\GGUF_Download' },
    @{ Name = 'llama';  Target = 'D:\llama.cpp' },
    @{ Name = 'wb';     Target = 'C:\Users\Ad\.workbuddy' }
)

if (-not (Test-Path $WorkspaceRoot)) {
    Write-Warning "工作区根不存在，将创建: $WorkspaceRoot"
    if (-not $DryRun) { New-Item -ItemType Directory -Path $WorkspaceRoot -Force | Out-Null }
}

foreach ($l in $links) {
    $path = Join-Path $WorkspaceRoot $l.Name
    $want = $l.Target
    if (Test-Path $path) {
        $item = Get-Item $path -Force
        $cur = if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { $item.Target } else { '(real dir)' }
        if ($cur -eq $want) { Log "OK  $($l.Name) → $want"; continue }
        if ($Force) {
            if ($DryRun) { Write-Host "[DRYRUN] 删除并重建 $($l.Name)" -ForegroundColor Yellow }
            else { $item.Delete(); New-Item -ItemType Junction -Path $path -Target $want | Out-Null; Log "重建 $($l.Name) → $want" }
        } else {
            Write-Warning "目标不符 $($l.Name): 当前=$cur 期望=$want（用 -Force 替换）"
        }
        continue
    }
    if (-not (Test-Path $want)) { Write-Warning "目标不存在，跳过 $($l.Name) → $want"; continue }
    if ($DryRun) { Write-Host "[DRYRUN] 新建 $($l.Name) → $want" -ForegroundColor Yellow }
    else { New-Item -ItemType Junction -Path $path -Target $want | Out-Null; Log "新建 $($l.Name) → $want" }
}

# 顺带：dsh profile 根 junction（C:\Users\Ad\.dsh → D:\Brain\dsh-data）
$profileLink = 'C:\Users\Ad\.dsh'
if (-not (Test-Path $profileLink)) {
    $target = Join-Path $BrainRoot 'dsh-data'
    if (Test-Path $target) {
        if ($DryRun) { Write-Host "[DRYRUN] 新建 profile junction" -ForegroundColor Yellow }
        else { New-Item -ItemType Junction -Path $profileLink -Target $target | Out-Null; Log "新建 .dsh → $target" }
    }
}

Log '完成。验证: dir <workspace-root> 应看到 7 个 junction；p/bench 与 p/memory 应可达。'
