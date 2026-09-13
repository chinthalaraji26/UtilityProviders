#!/usr/bin/env python3
"""Render Mermaid diagram source into a PNG file.

Primary path: mermaid.ink (no local dependencies, just network access).
Fallback path: local Mermaid CLI via `npx @mermaid-js/mermaid-cli` (used
automatically if mermaid.ink is unreachable or errors, or if --local is
passed explicitly).

Usage:
    python render.py --file diagram.mmd --out diagram.png
    python render.py --code "graph TD; A-->B;" --out diagram.png
    echo "graph TD; A-->B;" | python render.py --out diagram.png

Options:
    --file PATH       Read Mermaid source from PATH
    --code TEXT       Mermaid source given directly on the command line
    --out PATH        Output PNG path (required)
    --theme NAME       default | dark | forest | neutral  (default: default)
    --bg COLOR         Background color, e.g. white, transparent, "#1e1e1e"
                        (default: white)
    --width N           Output width in px (mermaid.ink only)
    --scale N           Scale factor, e.g. 2 for 2x resolution (mermaid.ink only)
    --local             Skip mermaid.ink and render locally via mermaid-cli
"""
import argparse
import base64
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request


def get_source(args) -> str:
    if args.code is not None:
        return args.code
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            return f.read()
    if not sys.stdin.isatty():
        data = sys.stdin.read()
        if data.strip():
            return data
    raise SystemExit("error: no Mermaid source given (use --code, --file, or stdin)")


def render_via_mermaid_ink(source: str, out_path: str, theme: str, bg: str,
                            width: int | None, scale: float | None) -> None:
    b64 = base64.b64encode(source.encode("utf-8")).decode("ascii")
    b64_path = urllib.parse.quote(b64, safe="")  # base64 can contain '/', '+' — must not be read as path separators
    params = {"type": "png", "theme": theme, "bgColor": bg}
    if width:
        params["width"] = str(width)
    if scale:
        # mermaid.ink rejects `scale` unless `width` or `height` is also set
        if not width:
            params["width"] = "800"
        params["scale"] = str(scale)
    url = f"https://mermaid.ink/img/{b64_path}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url, headers={"User-Agent": "mermaid-to-png-skill"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f"mermaid.ink returned HTTP {resp.status}")
        data = resp.read()

    if not data.startswith(b"\x89PNG"):
        raise RuntimeError("mermaid.ink did not return a valid PNG (diagram may have a syntax error)")

    with open(out_path, "wb") as f:
        f.write(data)


def render_via_local_cli(source: str, out_path: str, theme: str, bg: str) -> None:
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False, encoding="utf-8") as tmp:
        tmp.write(source)
        tmp_path = tmp.name
    try:
        cmd = [
            "npx", "-y", "@mermaid-js/mermaid-cli",
            "-i", tmp_path,
            "-o", out_path,
            "-t", theme,
            "-b", bg,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, shell=(os.name == "nt"))
        if result.returncode != 0:
            raise RuntimeError(f"mermaid-cli failed:\n{result.stdout}\n{result.stderr}")
    finally:
        os.unlink(tmp_path)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--file")
    p.add_argument("--code")
    p.add_argument("--out", required=True)
    p.add_argument("--theme", default="default")
    p.add_argument("--bg", default="white")
    p.add_argument("--width", type=int, default=None)
    p.add_argument("--scale", type=float, default=None)
    p.add_argument("--local", action="store_true", help="render locally via mermaid-cli, skip mermaid.ink")
    args = p.parse_args()

    source = get_source(args)

    if args.local:
        render_via_local_cli(source, args.out, args.theme, args.bg)
        print(f"Rendered (local mermaid-cli) -> {args.out}")
        return

    try:
        render_via_mermaid_ink(source, args.out, args.theme, args.bg, args.width, args.scale)
        print(f"Rendered (mermaid.ink) -> {args.out}")
    except (urllib.error.URLError, RuntimeError, TimeoutError) as e:
        print(f"mermaid.ink failed ({e}); falling back to local mermaid-cli...", file=sys.stderr)
        render_via_local_cli(source, args.out, args.theme, args.bg)
        print(f"Rendered (local mermaid-cli) -> {args.out}")


if __name__ == "__main__":
    main()
