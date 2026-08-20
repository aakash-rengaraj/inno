<#
.SYNOPSIS
  One-shot setup of the Price Review app on a fresh Windows VPS.

.DESCRIPTION
  Installs the prerequisites, clones the repo, builds both surfaces, registers
  the app as a Windows service, and schedules the two-minute sync from main.

  Safe to re-run. Every step checks for what it is about to create, so a run
  that fails halfway can simply be run again rather than unpicked by hand.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File bootstrap.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File bootstrap.ps1 -Port 80 -Token 'something-else'
#>
[CmdletBinding()]
param(
  [string]$RepoUrl  = "https://github.com/aakash-rengaraj/inno",
  [string]$Root     = "C:\apps\innohack",
  [string]$Branch   = "main",
  [string]$Service  = "InnoHack",
  [int]   $Port     = 8000,
  [string]$Token    = "vellore-dso-2026",
  [int]   $RateLimit = 30,
  [string]$Origins  = "*",
  [switch]$SkipSync          # set up the app but not the auto-deploy task
)

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"   # winget/Invoke-WebRequest are far
                                              # slower with a progress bar on
$script:Steps = @()

function Log  ($m) { Write-Host "  $m" }
function Step ($m) { Write-Host "`n== $m" -ForegroundColor Cyan; $script:Steps += $m }
function Warn ($m) { Write-Host "  ! $m" -ForegroundColor Yellow }
function Die  ($m) { Write-Host "`nFAILED: $m" -ForegroundColor Red; exit 1 }

function Assert-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $pr = New-Object Security.Principal.WindowsPrincipal($id)
  if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Die "Run this from an elevated PowerShell (Run as Administrator). Registering a service and a SYSTEM scheduled task both need it."
  }
}

# winget installs write to the machine PATH, but this process inherited its
# environment at launch and will not see them. Re-read both scopes after each
# install rather than telling the operator to open a new window.
function Sync-Path {
  $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
  $user    = [Environment]::GetEnvironmentVariable("Path", "User")
  $env:Path = ($machine, $user | Where-Object { $_ }) -join ";"
}

function Have ($exe) { [bool](Get-Command $exe -ErrorAction SilentlyContinue) }

function Install-WithWinget ($id, $exe, $label) {
  if (Have $exe) { Log "$label already present ($((Get-Command $exe).Source))"; return $true }
  if (-not (Have "winget")) { return $false }
  Log "installing $label via winget ($id)"
  winget install --id $id --exact --silent --accept-source-agreements `
                 --accept-package-agreements --disable-interactivity | Out-Null
  Sync-Path
  return (Have $exe)
}

# ---------------------------------------------------------------------------
Assert-Admin
Write-Host "Price Review - Windows VPS bootstrap" -ForegroundColor White
Write-Host "  repo    $RepoUrl ($Branch)"
Write-Host "  root    $Root"
Write-Host "  service $Service on port $Port"

Step "Prerequisites"

if (-not (Have "winget")) {
  Warn "winget is not installed - common on Windows Server images."
  Warn "Install App Installer from https://aka.ms/getwinget, or install Git,"
  Warn "Python 3.12 and Node 20 by hand, then re-run this script."
}

if (-not (Install-WithWinget "Git.Git" "git" "Git")) {
  Die "Git not available. Install from https://git-scm.com/download/win and re-run."
}

if (-not (Install-WithWinget "Python.Python.3.12" "python" "Python")) {
  Die "Python not available. Install 3.12 from https://python.org/downloads/ (tick 'Add to PATH') and re-run."
}

# A fresh Windows ships a "python.exe" stub that only opens the Microsoft Store.
# It is on PATH and answers Get-Command, so the presence check above can pass
# while every later call silently does nothing.
$pyver = (& python --version 2>&1) -join ""
if ($pyver -notmatch "Python 3\.(1[1-9]|[2-9]\d)") {
  Warn "'python' resolved to '$pyver'"
  Die "That is the Microsoft Store alias, not a real Python. Turn it off under Settings > Apps > Advanced app settings > App execution aliases, or install Python 3.12 from python.org with 'Add to PATH' ticked, then re-run."
}
Log "using $pyver"

if (-not (Install-WithWinget "OpenJS.NodeJS.LTS" "npm" "Node.js LTS")) {
  Die "Node not available. Install the LTS MSI from https://nodejs.org/ and re-run."
}

# LightGBM's Windows wheel bundles its own OpenMP (no libomp step as on macOS)
# but still links against the VC++ runtime. Most Server images have it; a fresh
# minimal one may not, and the failure is an opaque DLL error at import.
Log "ensuring VC++ 2015-2022 redistributable"
try {
  winget install --id Microsoft.VCRedist.2015+.x64 --exact --silent `
    --accept-source-agreements --accept-package-agreements --disable-interactivity | Out-Null
} catch { Warn "could not confirm VC++ redistributable - if LightGBM fails to import, install it by hand" }

# NSSM: Windows has no systemd, and a scheduled task at logon dies with the
# session. winget carries it, but fall back to the official zip.
$nssm = "C:\nssm\nssm.exe"
if (Have "nssm") {
  $nssm = (Get-Command nssm).Source
  Log "NSSM already present ($nssm)"
} elseif (Test-Path $nssm) {
  Log "NSSM already present ($nssm)"
} elseif (Install-WithWinget "NSSM.NSSM" "nssm" "NSSM") {
  $nssm = (Get-Command nssm).Source
} else {
  Log "downloading NSSM from nssm.cc"
  $zip = Join-Path $env:TEMP "nssm.zip"
  Invoke-WebRequest "https://nssm.cc/release/nssm-2.24.zip" -OutFile $zip
  Expand-Archive $zip -DestinationPath "C:\nssm-tmp" -Force
  New-Item -ItemType Directory -Force -Path "C:\nssm" | Out-Null
  Copy-Item "C:\nssm-tmp\nssm-2.24\win64\nssm.exe" $nssm -Force
  Remove-Item "C:\nssm-tmp", $zip -Recurse -Force
}
if (-not (Test-Path $nssm)) { Die "NSSM unavailable - install from https://nssm.cc/ and re-run." }

Step "Source"

# This script only ever builds what is at $Root. If you launched a copy from
# Downloads or a ZIP, that copy is not what gets deployed -- the clone below is
# reset to origin/$Branch first, so anything not pushed is not here.
if ($PSScriptRoot -and -not $PSScriptRoot.StartsWith($Root, "OrdinalIgnoreCase")) {
  Warn "running from $PSScriptRoot but deploying $Root from origin/$Branch"
  Warn "unpushed local changes will NOT be deployed"
}

if (Test-Path (Join-Path $Root ".git")) {
  Log "repo already at $Root - fetching $Branch"
  Push-Location $Root
  git fetch origin $Branch --quiet
  git reset --hard "origin/$Branch" --quiet
  Pop-Location
} else {
  New-Item -ItemType Directory -Force -Path (Split-Path $Root) | Out-Null
  Log "cloning into $Root"
  git clone --branch $Branch $RepoUrl $Root
}
Push-Location $Root
Log ("at " + (git rev-parse --short HEAD))

Step "Python environment"

$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  Log "creating .venv"
  python -m venv .venv
  if (-not (Test-Path $py)) { Die "venv creation produced no python.exe at $py" }
}

# Always `python -m pip`, never pip.exe. Two reasons, both bit us:
#   - pip.exe refuses to upgrade itself on Windows ("To modify pip, please run
#     ...python.exe -m pip"), and a native command's failure does not trip
#     $ErrorActionPreference, so the script sailed past it.
#   - `pip` resolved from PATH is the *system* pip even when the current
#     directory is .venv\Scripts. Packages land in global site-packages and the
#     venv never sees them, which is exactly how xmlschema went missing twice.
Log "upgrading pip in the venv"
& $py -m pip install --quiet --upgrade pip
if ($LASTEXITCODE -ne 0) { Warn "pip self-upgrade failed - continuing with the existing version" }

Log "installing requirements (pandas, lightgbm, fastapi - takes a few minutes)"
& $py -m pip install --quiet -r requirements.txt
if ($LASTEXITCODE -ne 0) { Die "pip install failed - re-run without --quiet to see why" }

# Prove the interpreter about to be used is the venv one and not the system
# install that happens to be first on PATH.
$site = (& $py -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
if ($site -notlike "$Root*") { Die "venv python is resolving packages to '$site', outside $Root" }
Log "site-packages: $site"

# Import every third-party module the build and the server actually use, not
# just the interesting one. `xmlschema` was missing from requirements.txt and
# surfaced 300 lines into pipeline.build, after the model had already been fitted.
Log "verifying imports"
& $py -c "import lightgbm, pandas, numpy, pyarrow, xmlschema, fastapi, pydantic, uvicorn, httpx; print('    lightgbm', lightgbm.__version__, '/ pandas', pandas.__version__)"
if ($LASTEXITCODE -ne 0) {
  Die "A dependency did not import. If it named lightgbm, it is usually the missing VC++ 2015-2022 x64 redistributable: https://aka.ms/vs/17/release/vc_redist.x64.exe. Otherwise re-run 'pip install -r requirements.txt' and read the error."
}

Step "Frontend"

# tools.build_web shells out to npx, not npm. On Windows that is npx.cmd, and
# Python's subprocess needs it resolvable via PATHEXT -- check it here rather
# than three minutes later, after pipeline.build has refitted the model.
if (-not (Have "npx")) {
  Die "npx not on PATH though npm is. Reopen an elevated shell so PATH is refreshed, or reinstall Node.js LTS."
}

Log "npm ci"
npm --prefix web ci --silent
if ($LASTEXITCODE -ne 0) { Die "npm ci failed" }

Step "Build"

Log "pipeline.build (offline - fits the band model, ~1 minute)"
& $py -m pipeline.build
if ($LASTEXITCODE -ne 0) { Die "pipeline.build failed" }

Log "tools.build_web (both surfaces)"
& $py -m tools.build_web
if ($LASTEXITCODE -ne 0) { Die "tools.build_web failed" }

Step "Service"

New-Item -ItemType Directory -Force -Path (Join-Path $Root "logs") | Out-Null

if (Get-Service -Name $Service -ErrorAction SilentlyContinue) {
  Log "service '$Service' exists - stopping to reconfigure"
  & $nssm stop $Service | Out-Null
} else {
  Log "registering service '$Service'"
  & $nssm install $Service $py | Out-Null
}

& $nssm set $Service AppParameters "-m uvicorn server.app:app --host 0.0.0.0 --port $Port" | Out-Null
& $nssm set $Service AppDirectory $Root | Out-Null
& $nssm set $Service AppStdout (Join-Path $Root "logs\out.log") | Out-Null
& $nssm set $Service AppStderr (Join-Path $Root "logs\err.log") | Out-Null
& $nssm set $Service AppRotateFiles 1 | Out-Null
& $nssm set $Service AppRotateBytes 10485760 | Out-Null
& $nssm set $Service Start SERVICE_AUTO_START | Out-Null
& $nssm set $Service AppExit Default Restart | Out-Null
& $nssm set $Service AppRestartDelay 5000 | Out-Null

# Environment for the service process. NSSM takes these as one NUL-free block of
# KEY=VALUE pairs; they are NOT inherited from this shell, so setting them with
# $env: here would silently do nothing.
& $nssm set $Service AppEnvironmentExtra `
    "CONSOLE_TOKEN=$Token" "REPORTS_PER_HOUR=$RateLimit" "ALLOWED_ORIGINS=$Origins" `
    "PYTHONUNBUFFERED=1" | Out-Null

Log "starting"
& $nssm start $Service | Out-Null

Step "Firewall"

$rule = "InnoHack $Port"
if (Get-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue) {
  Log "rule '$rule' already present"
} else {
  New-NetFirewallRule -DisplayName $rule -Direction Inbound -Protocol TCP `
    -LocalPort $Port -Action Allow | Out-Null
  Log "opened TCP $Port"
}
Warn "Your VPS provider's own firewall is separate - open $Port there too."

if (-not $SkipSync) {
  Step "Auto-deploy"

  $task = "InnoHack sync"
  if (Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue) {
    Log "task '$task' already registered"
  } else {
    $sync = Join-Path $Root "deploy\sync.ps1"
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument `
      "-NoProfile -ExecutionPolicy Bypass -File `"$sync`" -Repo `"$Root`" -Branch $Branch -Service $Service"
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
      -RepetitionInterval (New-TimeSpan -Minutes 2)
    Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger `
      -User "SYSTEM" -RunLevel Highest -Force | Out-Null
    Log "polling $Branch every 2 minutes as SYSTEM"
  }
}

Step "Checking it answers"

$ok = $false
foreach ($i in 1..30) {
  Start-Sleep -Seconds 2
  try {
    $h = Invoke-RestMethod "http://localhost:$Port/api/health" -TimeoutSec 3
    Log "health: $($h.flags_in_queue) flag(s) in queue"
    $ok = $true
    break
  } catch { if ($i -eq 1) { Log "waiting for the band model to fit (~10s)" } }
}

Pop-Location

if (-not $ok) {
  Warn "no response on :$Port after 60s. Check $Root\logs\err.log and 'nssm status $Service'."
  exit 1
}

Write-Host "`nReady." -ForegroundColor Green
Write-Host "  public page  http://<this-host>:$Port/"
Write-Host "  console      http://<this-host>:$Port/console   passphrase: $Token"
Write-Host "  logs         $Root\logs\err.log"
Write-Host "  service      nssm restart $Service"
Write-Host ""
Write-Host "  Not yet done: TLS. The console passphrase travels in a header, so" -ForegroundColor Yellow
Write-Host "  over plain HTTP it is readable in transit. See deploy/README.md." -ForegroundColor Yellow
