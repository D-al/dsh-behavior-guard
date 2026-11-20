# sync-to-profile.ps1 —— 把权威仓库的治理文档同步到 dsh 能读到的 p/bench（真实文件，非 junction）
# 背景：AGENTS.md 声明"目标状态以 p/bench/ROADMAP.md 为准"，但 p/bench 曾是空目录，
#       导致 dsh 读不到治理文档、只能依赖人机会话传递——2026-11-19 整治。
# 用法：powershell -ExecutionPolicy Bypass -File D:\Brain\publish\dsh-behavior-guard\setup\sync-to-profile.ps1
# 幂等：可重复运行；每次覆盖为目标状态。

$ErrorActionPreference = 'Stop'
$SRC = 'D:\Brain\publish\dsh-behavior-guard'
$DST = 'D:\Brain\dsh-data\profiles\desktop\p\bench'

Write-Host "══ 治理文档同步 $SRC -> $DST ══"

if (-not (Test-Path $SRC)) { throw "权威仓库不存在: $SRC" }
if (-not (Test-Path $DST)) { New-Item -ItemType Directory -Path $DST -Force | Out-Null }

# 顶层治理文档
foreach ($f in @('ROADMAP.md','ROADMAP_GRAPH.md','CHANGELOG.md','README.md')) {
    Copy-Item (Join-Path $SRC $f) (Join-Path $DST $f) -Force
    Write-Host "[同步] $f"
}

# 子目录（docs / decisions / skills）
foreach ($sub in @('docs','decisions','skills')) {
    $s = Join-Path $SRC $sub
    $d = Join-Path $DST $sub
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
    if (Test-Path $s) {
        Get-ChildItem $s -File -ErrorAction SilentlyContinue | ForEach-Object {
            Copy-Item $_.FullName (Join-Path $d $_.Name) -Force
        }
        Write-Host "[同步] $sub/ ($((Get-ChildItem $s -File).Count) 文件)"
    }
}

Write-Host "`n完成。dsh 可通过 p/bench/ 读到最新治理文档。"
Write-Host "提醒：每次 git pull 权威仓库后运行本脚本，或在升级流程中调用。"
