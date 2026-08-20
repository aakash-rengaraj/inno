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

## Setup

From an **elevated** PowerShell on a fresh VPS:

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
irm https://raw.githubusercontent.com/aakash-rengaraj/inno/main/deploy/bootstrap.ps1 -OutFile bootstrap.ps1
.\bootstrap.ps1
```

`bootstrap.ps1` does the whole thing: installs Git, Python 3.12, Node LTS, the
VC++ redistributable and NSSM; clones to `C:\apps\innohack`; creates the venv;
`npm ci`; runs `pipeline.build` and `tools.build_web`; registers the service with
its environment; opens the firewall port; schedules the sync task; then polls
`/api/health` and refuses to report success until the app actually answers.

It is **safe to re-run** — every step checks for what it is about to create, so a
run that fails halfway can just be run again.

Options:

```powershell
.\bootstrap.ps1 -Port 80 -Token 'something-else' -Root 'D:\innohack'
.\bootstrap.ps1 -SkipSync        # no auto-deploy task
```

| | default |
|---|---|
| `-RepoUrl` | `https://github.com/aakash-rengaraj/inno` |
| `-Root` | `C:\apps\innohack` |
| `-Port` | `8000` |
| `-Token` | `vellore-dso-2026` (`CONSOLE_TOKEN`) |
| `-RateLimit` | `30` (`REPORTS_PER_HOUR`) |
| `-Origins` | `*` (`ALLOWED_ORIGINS`) |

Sizing: idle is ~46 MB, but a recompute peaks around **645 MB** — the band model
fit plus 216k observations in pandas. Give the box at least 2 GB.

### Installing into the venv, not the system Python

Use `python.exe -m pip`, with the venv's interpreter by full path:

```powershell
C:\apps\innohack\.venv\Scripts\python.exe -m pip install <package>
```

Being *inside* `.venv\Scripts` does not help — PowerShell does not search the
current directory, so a bare `pip` resolves from `PATH` to the system install and
the package lands in global site-packages where the venv will never see it. The
symptom is `Requirement already satisfied` followed by `ModuleNotFoundError` for
the same package. `bootstrap.ps1` now asserts that the venv resolves
`site-packages` inside `$Root` before it builds anything.

`pip.exe install --upgrade pip` also fails on Windows by design — pip cannot
replace a running executable. It prints `To modify pip, please run ...python.exe
-m pip`, and because a native command's exit code does not trip PowerShell's
`$ErrorActionPreference`, a script will sail straight past it.

### `SERVICE_PAUSED in response to START control`

NSSM's throttle. The app started, exited within ~1.5 seconds, and NSSM paused
rather than restart-looping. It always means uvicorn crashed on startup; it never
means the service is misconfigured in NSSM itself.

The reason is in `logs\err.log` — `bootstrap.ps1` prints the last 30 lines
automatically when the health check fails. To see it live:

```powershell
cd C:\apps\innohack
.venv\Scripts\python.exe -m uvicorn server.app:app --host 0.0.0.0 --port 8000
```

Usual causes, in order:

- **Port already in use.** Another uvicorn, or a previous run of this service,
  still holds 8000. Bootstrap now checks before registering and names the owning
  process. `Get-NetTCPConnection -LocalPort 8000 -State Listen`
- **A dependency missing from the venv** — the same failure mode as `xmlschema`.
  The service runs the venv's python by full path, so a package installed into
  the system Python is invisible to it.
- **`data/processed/observations.parquet` absent**, because `pipeline.build` did
  not finish. The engine parses `data/raw` at startup and exits if it cannot.
- **An import error for `server`.** The service runs with `--app-dir` so `$Root`
  is on `sys.path` regardless of the working directory. Running uvicorn by hand
  from some other folder needs the same flag, or a `cd` to the repo root first.

`nssm status InnoHack` reports the state; `nssm reset InnoHack` clears a paused
one so it can be started again.

### Things that go wrong on Windows specifically

**`winget` is missing.** Common on Windows Server images. Install App Installer
from <https://aka.ms/getwinget>, or install Git, Python 3.12 and Node 20 by hand
and re-run — the script detects each one and skips what is already there.

**`python` is the Microsoft Store stub.** Windows ships a `python.exe` that only
opens the Store. It is on `PATH` and answers `Get-Command`, so a naive presence
check passes while every later call silently does nothing. The script runs
`python --version` and refuses to continue if it does not see a real 3.11+.
Fix under *Settings > Apps > Advanced app settings > App execution aliases*.

**LightGBM will not import.** Almost always the missing VC++ 2015-2022 x64
redistributable — <https://aka.ms/vs/17/release/vc_redist.x64.exe>. The Windows
wheel bundles its own OpenMP, so there is no `libomp` step like on macOS. The
script installs the redistributable and then verifies the import, so this fails
loudly at setup rather than at the first request.

**`npx` not found from Python.** `tools.build_web` shells out to npx, which on
Windows is `npx.cmd`. `CreateProcess` does not apply `PATHEXT`, so a bare `"npx"`
matches no file and raises `FileNotFoundError: [WinError 2]`. Resolved with
`shutil.which`, which does consult `PATHEXT`. Nothing to do on the VPS beyond
having Node on `PATH` — noted because the traceback points at `subprocess` and
says nothing about Node.

**Service environment.** NSSM does not inherit this shell's variables, so
`CONSOLE_TOKEN` has to be set with `AppEnvironmentExtra`. Setting `$env:` before
starting the service would silently do nothing.

### Doing it by hand

If you would rather not run a script, `bootstrap.ps1` reads top to bottom as the
manual procedure — each `Step` is one stage, and the `nssm set` and
`Register-ScheduledTask` calls can be pasted as-is.

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

## Putting it on a domain (Cloudflare)

The app listens on 8000, and **Cloudflare's proxy does not support that port** —
proxied HTTP is 80, 8080, 8880, 2052, 2082, 2086, 2095 only. An orange-clouded
record pointing at :8000 will not reach it. Rather than move the app to 8080 and
run unencrypted behind the proxy, put Caddy on 443 in front of it, which is what
the TLS note below asks for anyway.

**1. Install Caddy on the VPS**

```powershell
winget install --id CaddyServer.Caddy --exact --silent
```

**2. Use `deploy/Caddyfile`** (edit the hostname if it is not `inno.aakashr.com`)

```powershell
Copy-Item C:\apps\innohack\deploy\Caddyfile C:\caddy\Caddyfile -Force
caddy run --config C:\caddy\Caddyfile      # foreground, to watch it get a cert
```

Once it works, register it as a service so it survives reboots:

```powershell
nssm install Caddy "C:\Program Files\Caddy\caddy.exe"
nssm set Caddy AppParameters "run --config C:\caddy\Caddyfile"
nssm set Caddy Start SERVICE_AUTO_START
nssm start Caddy
```

**3. Open 80 and 443** — 80 is not optional, Let's Encrypt validates over it.

```powershell
New-NetFirewallRule -DisplayName "HTTP"  -Direction Inbound -Protocol TCP -LocalPort 80  -Action Allow
New-NetFirewallRule -DisplayName "HTTPS" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
```

Your VPS provider's own firewall needs the same two rules.

**4. DNS in the Cloudflare dashboard** — `aakashr.com` > DNS > Add record

| | |
|---|---|
| Type | `A` |
| Name | `inno` |
| IPv4 | `84.54.33.44` |
| Proxy | **DNS only (grey) at first**, orange once the certificate is issued |

Grey-cloud for the first run. With the proxy on, Cloudflare answers the HTTP-01
challenge path itself and Caddy can fail to validate; issuing first over a direct
connection avoids a confusing loop. Flip to orange straight after.

**5. SSL/TLS mode: Full (strict)**

Under SSL/TLS > Overview. `Flexible` would leave Cloudflare-to-origin on plain
HTTP, which puts the console passphrase back in cleartext for the longest leg of
the journey. Caddy has a real certificate, so `Full (strict)` just works.

**6. Close the back door**

With the domain live, `http://84.54.33.44:8000` is still open, unencrypted, and
bypasses Cloudflare entirely. Bind the app to loopback and shut the port:

```powershell
nssm set InnoHack AppParameters "-m uvicorn server.app:app --host 127.0.0.1 --port 8000"
nssm restart InnoHack
Remove-NetFirewallRule -DisplayName "InnoHack 8000"
```

`ALLOWED_ORIGINS` can stay unset — the app serves both surfaces itself, so every
request is same-origin.

## Keeping Agmarknet current

The committed export is a snapshot. Detection runs on the last 90 days, so a
stale export slowly empties the queue — the data does not go wrong, it goes
quiet, which is worse. `tools/refresh_agmarknet.py` tops it up from the
data.gov.in open-data API.

```powershell
[Environment]::SetEnvironmentVariable('DATA_GOV_API_KEY','<key>','Machine')
```

Machine scope, not a task argument: a scheduled task's command line is readable
by anyone who can list tasks, and this is a credential. Set it, then re-run
`bootstrap.ps1` and it registers `deploy/refresh.ps1` to run **every 2 days at
02:15** as SYSTEM. Run it by hand any time:

```powershell
.venv\Scripts\python.exe -m tools.refresh_agmarknet --dry-run   # fetch, report, write nothing
.venv\Scripts\python.exe -m tools.refresh_agmarknet
```

What one run looks like:

```
Vellore page 1: 346 rows      392 of 523 rows are markets the panel already models
Ranipet page 1: 99 rows       +392 rows -> 247,274 total, through 2026-08-20
Thirupathur page 1: 78 rows
```

**The resource only serves current prices, not history.** Each run captures a few
days and the committed file accumulates the rest. A run that is missed is data
that cannot be fetched later — which is the argument for a schedule rather than
doing it by hand before the demo.

**`refresh.ps1` restarts the service, but only if the export changed.** The
server fits its band model once at startup and reuses it for per-report
recomputes, so new source data is invisible until it restarts. Nothing changed
means no restart and no rebuild, which is what makes a 2-day schedule cheap.

**Fetching stays separate from building.** The refresh writes to `data/raw` and
stops there; `pipeline.build` still reads only from disk and opens no socket. The
offline guarantee is intact — verify with the wifi off.

### Two things the API does that look like network faults

**It stalls on the default `python-httpx` User-Agent.** The request is accepted
and then never answered, so it surfaces as `ReadTimeout` rather than a 403.
Measured: default httpx timed out at 15s three times; `curl/8.7.1` and the UA
this module sends both returned 200 in under a second.

**Under load it answers `200` with `{"message": "No query was recieved",
"records": []}`**, which is indistinguishable from a genuinely empty result. An
earlier version read that as end-of-data and reported a successful run having
fetched nothing. It now backs off and retries, and fails loudly rather than
quietly succeeding.

## Before it faces the internet

- **TLS.** The console passphrase travels in the `X-Console-Token` header, so
  over plain HTTP it is readable in transit. Put IIS or Caddy in front on :443
  and proxy to :8000. Caddy gets a certificate on its own with one line:
  `yourdomain.com { reverse_proxy localhost:8000 }`
- `REPORTS_PER_HOUR` (default 30/IP) throttles the open intake endpoint.
- `ALLOWED_ORIGINS` only matters if the pages are served from another host. When
  this app serves both surfaces it can stay unset.
