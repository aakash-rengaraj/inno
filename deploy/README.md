# Windows VPS deployment

Auto-syncs from `main` by polling. Two moving parts: a Windows **service** that
keeps the app running, and a **scheduled task** that pulls and restarts it.

## Why polling and not GitHub Actions

The obvious answer is a self-hosted Actions runner on the VPS. Don't — the repo
is public, and [GitHub's own guidance][gh] is not to pair the two: a workflow
that triggers on pull requests will execute a stranger's code on your box, as
whatever user the runner runs as. There is no setting that makes that fully safe
on a public repo; the recommended fix is not to do it.

Polling also needs **no inbound port** for deployment, no webhook endpoint, and
no secret shared with GitHub. It is strictly less machinery.

The tradeoff is latency: changes land within the poll interval rather than
instantly. At a 2-minute interval that has never mattered for a demo.

[gh]: https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners#self-hosted-runner-security

## One-time setup

Install Git, Python 3.12, Node 20, and [NSSM](https://nssm.cc/) (to run uvicorn
as a service — Windows has no `systemd`, and a scheduled task at logon dies with
the session).

```powershell
git clone https://github.com/aakash-rengaraj/inno C:\apps\innohack
cd C:\apps\innohack
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
npm --prefix web ci
.venv\Scripts\python -m pipeline.build
.venv\Scripts\python -m tools.build_web
```

LightGBM's Windows wheel bundles its own OpenMP, so there is no `libomp` step
like on macOS. It does need the Visual C++ 2015-2022 redistributable, which most
Windows Server images already carry.

### Register the service

```powershell
nssm install InnoHack C:\apps\innohack\.venv\Scripts\python.exe
nssm set InnoHack AppParameters "-m uvicorn server.app:app --host 0.0.0.0 --port 8000"
nssm set InnoHack AppDirectory C:\apps\innohack
nssm set InnoHack AppEnvironmentExtra CONSOLE_TOKEN=vellore-dso-2026 REPORTS_PER_HOUR=30
nssm set InnoHack AppStdout C:\apps\innohack\logs\out.log
nssm set InnoHack AppStderr C:\apps\innohack\logs\err.log
nssm set InnoHack AppExit Default Restart
nssm start InnoHack
```

Sizing: idle is ~46 MB, but a recompute peaks around **645 MB** — the band model
fit plus 216k observations in pandas. Give the box at least 2 GB.

### Register the sync task

Every 2 minutes, whether or not anyone is logged in:

```powershell
$action  = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File C:\apps\innohack\deploy\sync.ps1"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
  -RepetitionInterval (New-TimeSpan -Minutes 2)
Register-ScheduledTask -TaskName "InnoHack sync" -Action $action -Trigger $trigger `
  -User "SYSTEM" -RunLevel Highest
```

Check it: `Get-ScheduledTaskInfo "InnoHack sync"`, and run
`powershell -File deploy\sync.ps1` by hand once to confirm it reaches GitHub.

### Open the port

```powershell
New-NetFirewallRule -DisplayName "InnoHack 8000" -Direction Inbound `
  -Protocol TCP -LocalPort 8000 -Action Allow
```

Your VPS provider's own firewall usually needs the same rule separately.

## What survives a deploy

`sync.ps1` does `git reset --hard`, not a merge — the VPS is a deploy target,
never a place work happens, and a stray local edit must not stall a deploy behind
a conflict.

`server/data/` is gitignored, so **citizen reports and the action board survive**
every deploy. To reset before a rehearsal, stop the service and delete
`server/data/review.db*`.

The build artifacts under `web/public/data/` are committed, so a pull normally
brings them along; `sync.ps1` only re-runs `pipeline.build` when something under
`pipeline/`, `tools/` or `data/raw/` actually moved, and only rebuilds the
frontends when `web/src` or the Vite config did.

## Before it faces the internet

- **TLS.** The console passphrase travels in the `X-Console-Token` header, so
  over plain HTTP it is readable in transit. Put IIS or Caddy in front on :443
  and proxy to :8000. Caddy gets a certificate on its own with one line:
  `yourdomain.com { reverse_proxy localhost:8000 }`
- `REPORTS_PER_HOUR` (default 30/IP) throttles the open intake endpoint.
- `ALLOWED_ORIGINS` only matters if the pages are served from another host. When
  this app serves both surfaces it can stay unset.
