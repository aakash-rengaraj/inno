<#
  Refresh the Agmarknet export from data.gov.in, rebuild, restart the service.

  Scheduled every two days. See deploy/README.md.

  The service fits its band model once at startup and reuses it for per-report
  recomputes, so new source data is not picked up until the service restarts.
  That is the last step here, and it only happens if the export actually changed.
#>
param(
  [string]$Repo    = "C:\apps\innohack",
  [string]$Service = "InnoHack"
)

$ErrorActionPreference = "Stop"
Set-Location $Repo

function Log($m) { Write-Output ("[{0}] {1}" -f (Get-Date -Format s), $m) }

if (-not $env:DATA_GOV_API_KEY) {
  # Not passed as a parameter: a scheduled task's arguments are readable by any
  # user who can list tasks, and this one is a credential.
  Log "ERROR: DATA_GOV_API_KEY is not set for this process"
  Log "  set it machine-wide:  [Environment]::SetEnvironmentVariable('DATA_GOV_API_KEY','<key>','Machine')"
  exit 1
}

$py = Join-Path $Repo ".venv\Scripts\python.exe"
$before = (Get-Item "data\raw\agmarknet_real\vellore_export.csv.gz").LastWriteTimeUtc

Log "refreshing"
& $py -m tools.refresh_agmarknet
if ($LASTEXITCODE -ne 0) { Log "refresh failed - leaving the running service alone"; exit 1 }

$after = (Get-Item "data\raw\agmarknet_real\vellore_export.csv.gz").LastWriteTimeUtc
if ($after -eq $before) { Log "export unchanged - not restarting"; exit 0 }

Log "restarting $Service to refit the band model"
Restart-Service -Name $Service -Force
Log "done"
