"""Assemble the built app into one self-contained HTML page.

The artifact host blocks every external request, so the bundle, the stylesheet
and all five JSON artifacts are inlined ahead of the script.

    npx vite build --prefix web && python -m tools.make_standalone
"""
from __future__ import annotations

import json
from pathlib import Path
from pipeline import paths

WEB = paths.WEB
DATA = WEB / "public" / "data"
OUT = paths.WEB / "dist" / "standalone.html"

NAMES = ["queue", "flags", "cases", "charts", "meta"]


def guard(text: str) -> str:
    """A literal </script> inside an inline script would close it early."""
    return text.replace("</script", "<\\/script")


def main() -> None:
    assets = sorted((WEB / "dist" / "assets").iterdir())
    css = next(p for p in assets if p.suffix == ".css").read_text()
    js = next(p for p in assets if p.suffix == ".js").read_text()
    payload = {n: json.loads((DATA / f"{n}.json").read_text()) for n in NAMES}

    html = f"""<title>FairMark — Vellore District</title>
<style>
{css}
/* The artifact host paints its own ground behind the page; this instrument is
   deliberately single-theme (it is meant to read as paper), so it paints its
   own background explicitly rather than borrowing the host's. */
html, body {{ background: var(--paper); color: var(--ink); }}
</style>
<div id="root"></div>
<script>window.__CASE_DATA__ = {guard(json.dumps(payload))};</script>
<script type="module">
{guard(js)}
</script>
"""
    OUT.write_text(html)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} kB)")


if __name__ == "__main__":
    main()
