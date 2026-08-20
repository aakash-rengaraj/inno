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

## Before it faces the internet

- **TLS.** The console passphrase travels in the `X-Console-Token` header, so
  over plain HTTP it is readable in transit. Put IIS or Caddy in front on :443
  and proxy to :8000. Caddy gets a certificate on its own with one line:
  `yourdomain.com { reverse_proxy localhost:8000 }`
- `REPORTS_PER_HOUR` (default 30/IP) throttles the open intake endpoint.
- `ALLOWED_ORIGINS` only matters if the pages are served from another host. When
  this app serves both surfaces it can stay unset.
