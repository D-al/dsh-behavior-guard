#Requires -Version 5.1
<#
.SYNOPSIS
  One-way (C -> D) mirror sync for the default-workspace "dual location" design.

.DESCRIPTION
  Source: C:\Users\Ad\Documents\deepseek-harness\default-workspace
          (real dir, dsh session-slug identity anchor, NEVER convert to junction)
  Target: D:\Brain\workspace\default-workspace
          (knowledge-asset archive inside the Brain)

  Rules:
    - Skip every junction / symlink on BOTH sides (never copy, follow, or modify them).
    - Real files: compare by SHA256, copy only when missing or different.
    - Real dirs: create when missing, then recurse.
    - Idempotent: running twice yields the same result.

.PARAMETER Src
  Source root. Default is the C-drive real workspace.

.PARAMETER Dst
  Target root. Default is the D-drive Brain mirror.

.PARAMETER DryRun
  Report what would change, write nothing.

.EXAMPLE
  .\setup\sync-default-workspace.ps1 -DryRun
  .\setup\sync-default-workspace.ps1
#>
param(
    [string]$Src = 'C:\Users\Ad\Documents\deepseek-harness\default-workspace',
    [string]$Dst = 'D:\Brain\workspace\default-workspace',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$script:addedFiles = 0
$script:updatedFiles = 0
$script:sameFiles = 0
$script:newDirs = 0
$script:skippedLinks = 0

function Test-IsLink {
    param([System.IO.FileSystemInfo]$Item)
    if ($null -eq $Item) { return $false }
    if (($Item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { return $true }
    $p = $Item.PSObject.Properties['LinkType']
    if ($null -ne $p -and $p.Value) { return $true }
    return $false
}

function Sync-Tree {
    param([string]$From, [string]$To)
    foreach ($it in (Get-ChildItem -LiteralPath $From -Force)) {
        $sp = $it.FullName
        $dp = Join-Path $To $it.Name

        if (Test-IsLink $it) {
            $script:skippedLinks++
            Write-Host "[SKIP link] $sp"
            continue
        }

        if ($it.PSIsContainer) {
            if (-not (Test-Path -LiteralPath $dp)) {
                $script:newDirs++
                Write-Host "[NEW dir ] $dp"
                if (-not $DryRun) { New-Item -ItemType Directory -Path $dp -Force | Out-Null }
            } else {
                $dt = Get-Item -LiteralPath $dp -Force
                if (Test-IsLink $dt) {
                    $script:skippedLinks++
                    Write-Host "[SKIP link] $dp (target)"
                    continue
                }
            }
            Sync-Tree -From $sp -To $dp
            continue
        }

        $dstItem = Get-Item -LiteralPath $dp -Force -ErrorAction SilentlyContinue
        if ($null -ne $dstItem -and (Test-IsLink $dstItem)) {
            $script:skippedLinks++
            Write-Host "[SKIP link] $dp (target)"
            continue
        }
        $need = $true
        $action = 'NEW'
        if ($null -ne $dstItem) {
            $h1 = (Get-FileHash -LiteralPath $sp -Algorithm SHA256).Hash
            $h2 = (Get-FileHash -LiteralPath $dp -Algorithm SHA256).Hash
            if ($h1 -eq $h2) {
                $script:sameFiles++
                $need = $false
            } else {
                $action = 'UPDATE'
            }
        }
        if (-not $need) { continue }

        if ($action -eq 'NEW') { $script:addedFiles++ } else { $script:updatedFiles++ }
        Write-Host ("[{0,6}] {1}" -f $action, $dp)
        if (-not $DryRun) {
            $parent = Split-Path -Parent $dp
            if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
            Copy-Item -LiteralPath $sp -Destination $dp -Force
        }
    }
}

if (-not (Test-Path -LiteralPath $Src)) { throw "Source root missing: $Src" }
if (-not (Test-Path -LiteralPath $Dst)) {
    if ($DryRun) { Write-Host "[DRYRUN] would create target root: $Dst" }
    else { New-Item -ItemType Directory -Path $Dst -Force | Out-Null }
}

Write-Host "SYNC $Src -> $Dst"
if ($DryRun) { Write-Host "MODE: DRYRUN (no writes)" }

Sync-Tree -From $Src -To $Dst

Write-Host ""
Write-Host "==== SYNC SUMMARY ===="
Write-Host ("Added files    : {0}" -f $script:addedFiles)
Write-Host ("Updated files  : {0}" -f $script:updatedFiles)
Write-Host ("Identical files: {0}" -f $script:sameFiles)
Write-Host ("New dirs       : {0}" -f $script:newDirs)
Write-Host ("Skipped links  : {0}" -f $script:skippedLinks)
Write-Host "======================"
