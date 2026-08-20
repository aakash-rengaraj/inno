"""Build both frontends for hosting behind the API server.

    python -m tools.build_web

Produces web/dist-public and web/dist-console, each with an index.html, ready to
be mounted at / and /console.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

WEB = Path("web")

# Vite copies the whole of web/public into every dist, so the public build was
# shipping flags.json, cases.json, cases.xml, charts.json and heatmap.json as
# static files -- readable by anyone who guesses the path, whatever the bundle
# renders. The live server already projects `meta` down to a whitelist in
# `engine.public_meta`; this does the same to the offline build, so the static
# fallback and the served surface withhold the same things.
PUBLIC_ARTIFACTS = {"meta.json"}


def build(surface: str, outdir: str, entry: str) -> None:
    print(f"building {surface} -> {outdir}")
    subprocess.run(["npx", "vite", "build", "--outDir", outdir],
                   cwd=WEB, check=True, env={**__import__("os").environ,
                                             "SURFACE": surface})
    out = WEB / outdir
    # StaticFiles(html=True) serves index.html; the public entry is report.html
    if entry != "index.html":
        shutil.copyfile(out / entry, out / "index.html")
        print(f"  {entry} -> index.html")
    if surface == "public":
        _strip_public_artifacts(out / "data")


def _strip_public_artifacts(data: Path) -> None:
    if not data.is_dir():
        return
    removed = []
    for f in sorted(data.iterdir()):
        if f.name not in PUBLIC_ARTIFACTS:
            f.unlink()
            removed.append(f.name)

    meta_path = data / "meta.json"
    if meta_path.exists():
        from server.engine import PUBLIC_META_FIELDS
        meta = json.loads(meta_path.read_text())
        kept = {k: v for k, v in meta.items() if k in PUBLIC_META_FIELDS}
        dropped = sorted(set(meta) - set(kept))
        meta_path.write_text(json.dumps(kept, indent=1) + "\n")
        print(f"  meta.json projected to {len(kept)} public field(s); "
              f"dropped {', '.join(dropped)}")
    if removed:
        print(f"  withheld from the public build: {', '.join(removed)}")


def main() -> None:
    build("public", "dist-public", "report.html")
    build("console", "dist-console", "index.html")
    print("\nserve both:  uvicorn server.app:app --port 8000")
    print("  /         public page")
    print("  /console  enforcement console")


if __name__ == "__main__":
    main()
