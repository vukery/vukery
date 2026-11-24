#!/usr/bin/env python3
"""Bring code in from the Mission Pinball Framework (MPF) with a clear origin.

This is how vukery brings in MPF code:

1. Fetch the file from GitHub at one pinned MPF commit (never a local install).
2. Copy it verbatim into vukery, adding only a header comment with a
   permalink to its exact origin and MPF's copyright line.
3. Append an entry to vukery/_mpf/NOTICE.
4. Commit right away, on its own, before anything is changed.

Examples:

    # a whole file
    scripts/import_mpf.py mpf/platforms/fast/communicators/net_nano.py \\
        vukery/platforms/fast/net_nano.py

    # one block (lines 23-37), appended to a vukery file
    scripts/import_mpf.py mpf/core/ball_search.py vukery/devices/ball_search.py \\
        --lines 23-37

    # see what would happen without writing anything
    scripts/import_mpf.py mpf/core/ball_search.py vukery/devices/ball_search.py --dry-run

Uses only the standard library, and runs on Python 3.10 or newer.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.request
from pathlib import Path

MPF_REPO = "missionpinball/mpf"
# Head of MPF's 0.57.x branch (version 0.57.6, 2026-09-30). Each import names exactly one commit.
PINNED_SHA = "9ef886f4f263db44704f09a87bfd11229036ab5c"
PINNED_VERSION = "0.57.6"
COPYRIGHT = "Copyright (c) The Mission Pinball Framework team and other contributors."
NOTICE_PATH = Path("vukery/_mpf/NOTICE")
COMMENT_PREFIX = {".py": "#", ".yaml": "#", ".yml": "#", ".toml": "#"}


def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], check=False, capture_output=True, text=True
    )
    if out.returncode != 0:
        sys.exit("error: not inside a git repository (imports are recorded as git commits)")
    return Path(out.stdout.strip())


def fetch(mpf_path: str, sha: str) -> str:
    url = f"https://raw.githubusercontent.com/{MPF_REPO}/{sha}/{mpf_path}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except Exception as exc:  # noqa: BLE001 - report any fetch failure plainly
        sys.exit(f"error: could not fetch {url}: {exc}")


def parse_lines(spec: str) -> tuple[int, int]:
    try:
        start_s, end_s = spec.split("-")
        start, end = int(start_s), int(end_s)
    except ValueError:
        sys.exit(f"error: --lines must look like 23-37, got {spec!r}")
    if start < 1 or end < start:
        sys.exit(f"error: bad line range {spec!r}")
    return start, end


def header(prefix: str, permalink: str, version: str) -> str:
    return (
        f"{prefix} Copied from the Mission Pinball Framework (MPF) {version}:\n"
        f"{prefix} {permalink}\n"
        f"{prefix} {COPYRIGHT}\n"
        f"{prefix} MIT License: see vukery/_mpf/NOTICE.\n"
    )


def git(*args: str, cwd: Path) -> None:
    result = subprocess.run(["git", *args], check=False, cwd=cwd)
    if result.returncode != 0:
        sys.exit(f"error: git {' '.join(args)} failed")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("mpf_path", help="path inside the MPF repo, e.g. mpf/core/ball_search.py")
    parser.add_argument("dest", help="vukery path to write, relative to the repo root")
    parser.add_argument("--lines", help="copy only this line range, e.g. 23-37")
    parser.add_argument(
        "--sha", default=PINNED_SHA, help="MPF commit (default: the pinned 0.57.6 commit)"
    )
    parser.add_argument("--version-label", default=None, help="MPF version shown in the header")
    parser.add_argument("--dry-run", action="store_true", help="print the result, change nothing")
    parser.add_argument(
        "--no-commit", action="store_true", help="write files but don't commit (not recommended)"
    )
    parser.add_argument(
        "--trailer",
        action="append",
        default=[],
        help="extra line for the commit message (repeatable)",
    )
    args = parser.parse_args()

    mpf_path = args.mpf_path.lstrip("/")
    if args.sha != PINNED_SHA and not args.version_label:
        sys.exit("error: when using --sha, also pass --version-label")
    version = args.version_label or PINNED_VERSION
    short = args.sha[:7]

    dest_rel = Path(args.dest)
    prefix = COMMENT_PREFIX.get(dest_rel.suffix)
    if prefix is None:
        sys.exit(f"error: don't know how to write a header comment for {dest_rel.suffix!r} files")

    root = repo_root()
    dest = root / dest_rel
    notice = root / NOTICE_PATH

    source = fetch(mpf_path, args.sha)
    permalink = f"https://github.com/{MPF_REPO}/blob/{args.sha}/{mpf_path}"

    if args.lines:
        start, end = parse_lines(args.lines)
        src_lines = source.splitlines(keepends=True)
        if end > len(src_lines):
            sys.exit(f"error: {mpf_path} has only {len(src_lines)} lines")
        body = "".join(src_lines[start - 1 : end])
        permalink += f"#L{start}-L{end}"
    else:
        if dest.exists():
            sys.exit(
                f"error: {dest_rel} already exists; a whole-file import must create a new file"
            )
        body = source

    # Whole files stay byte-for-byte identical after the header, even if MPF's
    # file has no final newline. A partial block gets one so the file stays valid
    # when it's appended to an existing vukery file.
    if args.lines and not body.endswith("\n"):
        body += "\n"
    block = header(prefix, permalink, version) + body

    if dest.exists():
        existing = dest.read_text(encoding="utf-8")
        new_content = existing + ("" if existing.endswith("\n") else "\n") + "\n" + block
    else:
        new_content = block

    what = f"lines {args.lines} of " if args.lines else ""
    entry = (
        f"\n{dest_rel.as_posix()}\n"
        f"    from: {what}{mpf_path} @ {args.sha} (MPF {version})\n"
        f"    permalink: {permalink}\n"
    )
    subject = f"import(mpf): {what}{mpf_path.removeprefix('mpf/')} @ {short}"
    message = (
        f"{subject}\n\n"
        f"Verbatim copy from MPF {version} into {dest_rel.as_posix()}, with only\n"
        f"a provenance header added.\n"
        f"{permalink}\n"
    )
    if args.trailer:
        message += "\n" + "\n".join(args.trailer) + "\n"

    if args.dry_run:
        print(f"--- would write {dest_rel} ---")
        print(block, end="")
        print(f"--- would append to {NOTICE_PATH} ---{entry}")
        print(f"--- would commit ---\n{message}")
        return

    # The import commit must contain only the import, so nothing else may be staged.
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], check=False, cwd=root)
    if staged.returncode != 0:
        sys.exit("error: other changes are staged; commit or unstage them first")
    for path in (dest_rel, NOTICE_PATH):
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", str(path)],
            check=False,
            cwd=root,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if dirty and (root / path).exists():
            sys.exit(f"error: {path} has uncommitted changes; commit them first")

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(new_content, encoding="utf-8")
    with notice.open("a", encoding="utf-8") as fh:
        fh.write(entry)

    print(f"wrote {dest_rel} and updated {NOTICE_PATH}")
    if args.no_commit:
        print("not committed (--no-commit). Commit it on its own before changing it.")
        return

    git("add", "--", str(dest_rel), str(NOTICE_PATH), cwd=root)
    git("commit", "-m", message, cwd=root)
    print("committed. Make changes in later commits.")


if __name__ == "__main__":
    main()
