#Requires -Version 5.1
<#
.SYNOPSIS
One-click install of the dsh-agent-harness bundle into the dsh desktop profile.

.DESCRIPTION
Idempotent installer for the dsh-behavior-guard plugin. It:
  1. Resolves DSH_HOME (process env -> user env -> default D:\Brain\dsh-data)
     and the desktop profile directory (<DSH_HOME>\profiles\desktop).
  2. Backs up package.json and pnpm-lock.yaml with a timestamp.
  3. Ensures dependencies["dsh-agent-harness"] is set (github spec by default,
     or link:<repo> when -UseLocal is given).
  4. Ensures dsh.profile.bundles contains 'dsh-agent-harness'.
  5. Runs dsh bundled pnpm install with DSH_HOME exported, cwd = profile dir.
  6. Verifies the installed plugin version and that index.mjs exists.

ASCII-only by design: Windows PowerShell 5.1 decodes UTF-8-without-BOM as GBK,
so any non-ASCII byte in this file would corrupt parsing.

.PARAMETER UseLocal
Install from this repository via link:<repo> instead of github:D-al/dsh-behavior-guard.

.PARAMETER DshHome
Override DSH_HOME. Resolution order: -DshHome, process env, user env, default.

.PARAMETER ProfileDir
Override the profile directory. Default: <DshHome>\profiles\desktop.

.EXAMPLE
.\setup\install.ps1
.\setup\install.ps1 -UseLocal
#>
param(
    [switch]$UseLocal,
    [string]$DshHome = '',
    [string]$ProfileDir = ''
)

$ErrorActionPreference = 'Stop'

# ---------- constants ----------
$PluginName     = 'dsh-agent-harness'
$GithubSpec     = 'github:D-al/dsh-behavior-guard'
$DefaultDshHome = 'D:\Brain\dsh-data'
$RepoRoot       = Split-Path -Parent $PSScriptRoot
$Stamp          = Get-Date -Format 'yyyyMMdd-HHmmss'

function Log([string]$msg)  { Write-Host ('[install] ' + $msg) }
function Fail([string]$msg) { Write-Host ('[install] ERROR: ' + $msg) -ForegroundColor Red; exit 1 }

# ---------- resolve DSH_HOME (process env is often empty in a fresh shell) ----------
if (-not $DshHome) { $DshHome = $env:DSH_HOME }
if (-not $DshHome) { $DshHome = [Environment]::GetEnvironmentVariable('DSH_HOME', 'User') }
if (-not $DshHome) { $DshHome = $DefaultDshHome }
$env:DSH_HOME = $DshHome   # export to child processes (node/pnpm)

if (-not $ProfileDir) { $ProfileDir = Join-Path $DshHome 'profiles\desktop' }

Log ('DSH_HOME   = ' + $DshHome)
Log ('ProfileDir = ' + $ProfileDir)

# ---------- preflight ----------
if (-not (Test-Path -LiteralPath $ProfileDir)) { Fail ('profile directory not found: ' + $ProfileDir) }
$PkgPath = Join-Path $ProfileDir 'package.json'
if (-not (Test-Path -LiteralPath $PkgPath)) { Fail ('profile package.json not found: ' + $PkgPath) }

# pnpm.cjs: prefer dsh-runtimes under DSH_HOME, then the legacy app path.
$PnpmCjs = Join-Path $DshHome 'dsh-runtimes\dsh-primary-runtime\dependencies\pnpm\bin\pnpm.cjs'
if (-not (Test-Path -LiteralPath $PnpmCjs)) {
    $PnpmCjs = 'D:\Deepseek Harness\resources\runtime\primary-runtime\dependencies\pnpm\bin\pnpm.cjs'
}
if (-not (Test-Path -LiteralPath $PnpmCjs)) { Fail 'pnpm.cjs not found under DSH_HOME or legacy path' }
Log ('pnpm.cjs   = ' + $PnpmCjs)

if ($UseLocal) {
    $Spec = 'link:' + ($RepoRoot -replace '\\', '/')
} else {
    $Spec = $GithubSpec
}
Log ('spec       = ' + $Spec)

# ---------- timestamped backups ----------
foreach ($f in @($PkgPath, (Join-Path $ProfileDir 'pnpm-lock.yaml'))) {
    if (Test-Path -LiteralPath $f) {
        $bak = $f + '.bak-' + $Stamp
        Copy-Item -LiteralPath $f -Destination $bak -Force
        Log ('backup: ' + $bak)
    } else {
        Log ('backup skipped (missing): ' + $f)
    }
}

# ---------- load package.json ----------
$pkg = Get-Content -LiteralPath $PkgPath -Raw -Encoding UTF8 | ConvertFrom-Json

# ---------- ensure dependency ----------
if (-not $pkg.dependencies) {
    $pkg | Add-Member -NotePropertyName 'dependencies' -NotePropertyValue (New-Object PSObject) -Force
}
if ($pkg.dependencies.PSObject.Properties.Name -contains $PluginName) {
    $pkg.dependencies.PSObject.Properties.Remove($PluginName)
}
$pkg.dependencies | Add-Member -NotePropertyName $PluginName -NotePropertyValue $Spec -Force
Log ('dependency set: ' + $PluginName + ' = ' + $Spec)

# ---------- ensure bundle ----------
if (-not $pkg.dsh) { $pkg | Add-Member -NotePropertyName 'dsh' -NotePropertyValue (New-Object PSObject) -Force }
if (-not $pkg.dsh.profile) { $pkg.dsh | Add-Member -NotePropertyName 'profile' -NotePropertyValue (New-Object PSObject) -Force }
$bundles = @()
if ($pkg.dsh.profile.bundles) {
    $bundles = @($pkg.dsh.profile.bundles | Where-Object { $_ -and ($_ -ne $PluginName) })
}
$bundles += $PluginName
$pkg.dsh.profile | Add-Member -NotePropertyName 'bundles' -NotePropertyValue $bundles -Force
Log ('bundle ensured: ' + $PluginName + ' (total ' + $bundles.Count + ')')

# ---------- write back (UTF-8 no BOM, keep all other fields) ----------
$json = $pkg | ConvertTo-Json -Depth 20
[System.IO.File]::WriteAllText($PkgPath, $json + [Environment]::NewLine, (New-Object System.Text.UTF8Encoding($false)))
Log ('wrote: ' + $PkgPath)

# ---------- pnpm install ----------
Log 'running node <pnpm.cjs> install'
Push-Location $ProfileDir
try {
    & node $PnpmCjs install
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0) { Fail ('pnpm install failed, exit code ' + $code + ' (backups kept)') }
Log 'pnpm install: OK'

# ---------- verification ----------
$pluginDir = Join-Path $ProfileDir ('node_modules\' + $PluginName)
$pluginPkg = Join-Path $pluginDir 'package.json'
$indexMjs  = Join-Path $pluginDir 'index.mjs'
if (-not (Test-Path -LiteralPath $pluginDir)) { Fail ('verification failed: plugin dir missing: ' + $pluginDir) }
if (-not (Test-Path -LiteralPath $indexMjs))  { Fail ('verification failed: index.mjs missing: ' + $indexMjs) }
$installedVersion = (Get-Content -LiteralPath $pluginPkg -Raw -Encoding UTF8 | ConvertFrom-Json).version
Log ('verified version   = ' + $installedVersion)
Log ('verified index.mjs = ' + (Test-Path -LiteralPath $indexMjs))
Write-Host ''
Log 'INSTALL SUCCESS. Restart dsh to load the bundle.'