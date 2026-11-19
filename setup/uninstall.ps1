#Requires -Version 5.1
<#
.SYNOPSIS
One-click uninstall of the dsh-agent-harness bundle from the dsh desktop profile.

.DESCRIPTION
Idempotent uninstaller for the dsh-behavior-guard plugin. It:
  1. Resolves DSH_HOME / profile dir using the same rules as install.ps1.
  2. Backs up package.json and pnpm-lock.yaml with a timestamp.
  3. Removes dependencies["dsh-agent-harness"].
  4. Removes 'dsh-agent-harness' from dsh.profile.bundles.
     (Both declarations must go: app-boot rewrites the manifest from bundles.)
  5. Runs dsh bundled pnpm install with DSH_HOME exported so removal takes effect.
  6. Verifies the plugin directory is gone from node_modules.

ASCII-only by design: Windows PowerShell 5.1 decodes UTF-8-without-BOM as GBK,
so any non-ASCII byte in this file would corrupt parsing.

.PARAMETER DshHome
Override DSH_HOME. Resolution order: -DshHome, process env, user env, default.

.PARAMETER ProfileDir
Override the profile directory. Default: <DshHome>\profiles\desktop.

.EXAMPLE
.\setup\uninstall.ps1
#>
param(
    [string]$DshHome = '',
    [string]$ProfileDir = ''
)

$ErrorActionPreference = 'Stop'

# ---------- constants ----------
$PluginName     = 'dsh-agent-harness'
$DefaultDshHome = 'D:\Brain\dsh-data'
$Stamp          = Get-Date -Format 'yyyyMMdd-HHmmss'

function Log([string]$msg)  { Write-Host ('[uninstall] ' + $msg) }
function Fail([string]$msg) { Write-Host ('[uninstall] ERROR: ' + $msg) -ForegroundColor Red; exit 1 }

# ---------- resolve DSH_HOME ----------
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

$PnpmCjs = Join-Path $DshHome 'dsh-runtimes\dsh-primary-runtime\dependencies\pnpm\bin\pnpm.cjs'
if (-not (Test-Path -LiteralPath $PnpmCjs)) {
    $PnpmCjs = 'D:\Deepseek Harness\resources\runtime\primary-runtime\dependencies\pnpm\bin\pnpm.cjs'
}
if (-not (Test-Path -LiteralPath $PnpmCjs)) { Fail 'pnpm.cjs not found under DSH_HOME or legacy path' }
Log ('pnpm.cjs   = ' + $PnpmCjs)

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

# ---------- remove dependency ----------
$removedDep = $false
if ($pkg.dependencies -and ($pkg.dependencies.PSObject.Properties.Name -contains $PluginName)) {
    $pkg.dependencies.PSObject.Properties.Remove($PluginName)
    $removedDep = $true
}
Log ('dependency removed = ' + $removedDep)

# ---------- remove from bundles ----------
$removedBundle = $false
if ($pkg.dsh -and $pkg.dsh.profile -and $pkg.dsh.profile.bundles) {
    $orig = @($pkg.dsh.profile.bundles)
    $kept = @($orig | Where-Object { $_ -and ($_ -ne $PluginName) })
    if ($kept.Count -ne $orig.Count) { $removedBundle = $true }
    $pkg.dsh.profile | Add-Member -NotePropertyName 'bundles' -NotePropertyValue $kept -Force
}
Log ('bundle removed   = ' + $removedBundle)

# ---------- write back (UTF-8 no BOM, keep all other fields) ----------
$json = $pkg | ConvertTo-Json -Depth 20
[System.IO.File]::WriteAllText($PkgPath, $json + [Environment]::NewLine, (New-Object System.Text.UTF8Encoding($false)))
Log ('wrote: ' + $PkgPath)

# ---------- pnpm install so removal takes effect ----------
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
if (Test-Path -LiteralPath $pluginDir) {
    Fail ('verification failed: plugin dir still present: ' + $pluginDir + ' (pnpm may have kept a stale copy; remove it manually)')
}
Log 'verified: plugin dir gone = True'
Write-Host ''
Log 'UNINSTALL SUCCESS. Restart dsh to unload the bundle.'