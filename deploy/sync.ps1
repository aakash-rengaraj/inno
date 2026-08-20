<#
  Pull main, rebuild only what changed, restart the service.

  Run on a schedule (see deploy/README.md). Polls outbound over HTTPS, so the
  VPS needs no inbound port open for deployment and no webhook endpoint.

  Deliberately NOT a GitHub Actions self-hosted runner. GitHub's own guidance is
  not to use self-hosted runners with public repositories: anyone can open a pull
  request, and a workflow that runs on it executes their code on your box. The
  repo is public, so this polls instead.
#>

param(
  [string]$Repo    = "C:\apps\innohack",
  [string]$Branch  = "main",
  [string]$Service = "InnoHack"
)

$ErrorActionPreference = "Stop"
Set-Location $Repo

function Log($m) { Write-Output ("[{0}] {1}" -f (Get-Date -Format s), $m) }

git fetch origin $Branch --quiet
$local  = git rev-parse HEAD
$remote = git rev-parse "origin/$Branch"

if ($local -eq $remote) { Log "no change ($($local.Substring(0,7)))"; exit 0 }

Log "$($local.Substring(0,7)) -> $($remote.Substring(0,7))"
$changed = git diff --name-only $local $remote

# Hard reset, not merge: the VPS is a deploy target, never a place work happens.
# A stray local edit must not be able to stall a deploy behind a merge conflict.
# server/data/ is gitignored, so the citizen reports and the action board survive.
git reset --hard "origin/$Branch" --quiet

$py = Join-Path $Repo ".venv\Scripts\python.exe"

if ($changed -match '^requirements\.txt$') {
  # `python -m pip`, never pip.exe: a bare `pip` resolves from PATH to the
  # system install, and the packages would land outside the venv.
  Log "requirements changed - installing"
  & $py -m pip install -q -r requirements.txt
  if ($LASTEXITCODE -ne 0) { Log "ERROR: pip install failed - not restarting"; exit 1 }
}
if ($changed -match '^web/package(-lock)?\.json$') {
  Log "npm manifest changed - installing"
  npm --prefix web ci
}

# The artifacts are committed, so a pull normally brings them along already.
# Rebuild only when the code that produces them moved.
if ($changed -match '^(pipeline|tools|data/raw)/') {
  Log "pipeline changed - rebuilding artifacts"
  & $py -m pipeline.build
}
if ($changed -match '^(web/src|web/public|web/index\.html|web/report\.html|web/vite\.config\.js|tools/build_web\.py)') {
  Log "frontend changed - rebuilding both surfaces"
  & $py -m tools.build_web
}

# Restart last: everything above can fail without taking the running site down.
if (Get-Service -Name $Service -ErrorAction SilentlyContinue) {
  Log "restarting $Service"
  Restart-Service -Name $Service -Force
} else {
  Log "WARNING: service '$Service' not found - start it manually"
}

Log "deployed $($remote.Substring(0,7))"
