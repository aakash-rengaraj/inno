"""Build both frontends for hosting behind the API server.

    python -m tools.build_web

Produces web/dist-public and web/dist-console, each with an index.html, ready to
be mounted at / and /console.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

WEB = Path("web")


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


def main() -> None:
    build("public", "dist-public", "report.html")
    build("console", "dist-console", "index.html")
    print("\nserve both:  uvicorn server.app:app --port 8000")
    print("  /         public page")
    print("  /console  enforcement console")


if __name__ == "__main__":
    main()
