"""Report how adopted files have drifted from lindsay-50.

For each entry in rhb_led_driver/adopted/manifest.toml:

  ours      our edits, vs. the upstream file at the pinned commit
  upstream  lindsay-50's edits to the file between the pinned commit and HEAD

Reads lindsay-50 with `git show`, so its working tree is never touched.

    python scripts/adopted_drift.py [--diff] [--lindsay PATH]
"""

import argparse
import difflib
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADOPTED = ROOT / "rhb_led_driver" / "adopted"
HEADER_END = "# --- end adoption header ---\n"


def git_show(repo: Path, rev: str, path: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "show", f"{rev}:{path}"], check=True, capture_output=True, text=True
    ).stdout


def strip_header(text: str) -> str:
    _, sep, body = text.partition(HEADER_END)
    return body if sep else text


def diff(a: str, b: str, a_name: str, b_name: str) -> list[str]:
    return list(difflib.unified_diff(a.splitlines(True), b.splitlines(True), a_name, b_name))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--diff", action="store_true", help="print the full diffs")
    parser.add_argument("--lindsay", type=Path, default=ROOT.parent / "lindsay-50", help="lindsay-50 checkout")
    args = parser.parse_args()

    with open(ADOPTED / "manifest.toml", "rb") as f:
        manifest = tomllib.load(f)

    for entry in manifest["file"]:
        local, upstream, commit, mode = entry["local"], entry["upstream"], entry["commit"], entry["mode"]
        pinned = git_show(args.lindsay, commit, upstream)
        head = git_show(args.lindsay, "HEAD", upstream)
        ours_text = strip_header((ROOT / local).read_text())

        theirs = diff(pinned, head, f"{upstream}@{commit}", f"{upstream}@HEAD")
        ours = diff(pinned, ours_text, f"{upstream}@{commit}", local) if mode == "verbatim" else []

        ours_label = f"n/a ({mode})" if mode != "verbatim" else ("modified" if ours else "unchanged")
        print(f"{local:<40} ours: {ours_label:<14} upstream: {'CHANGED' if theirs else 'unchanged'}")
        if args.diff:
            sys.stdout.writelines(ours + theirs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
