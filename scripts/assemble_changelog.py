#!/usr/bin/env python3
"""Fold changelog.d/ fragments into CHANGELOG.md. Fragments are `<slug>.<type>.md`; the body is the bullet(s).

  python3 scripts/assemble_changelog.py --release 1.0.0   # write a dated section and clear the queue
  python3 scripts/assemble_changelog.py --preview          # print what a release would look like

Never hand-edit CHANGELOG.md — the queue is the source, so parallel branches don't conflict on one anchor.
"""
import argparse
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "changelog.d"
CHANGELOG = ROOT / "CHANGELOG.md"
ORDER = ["added", "changed", "deprecated", "removed", "fixed", "security"]
HEAD = "# Changelog\n\nEvery release folds the fragments queued in [`changelog.d/`](./changelog.d) into a dated section.\n"


def collect() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for f in sorted(QUEUE.glob("*.md")):
        if f.name == "README.md":
            continue
        parts = f.stem.rsplit(".", 1)
        kind = parts[1].lower() if len(parts) == 2 else "changed"
        if kind not in ORDER:
            raise SystemExit(f"{f.name}: unknown type '{kind}' (use {', '.join(ORDER)})")
        body = f.read_text().strip()
        if body:
            out.setdefault(kind, []).append(body)
    return out


def render(version: str, groups: dict[str, list[str]]) -> str:
    day = dt.date.today().isoformat()
    lines = [f"## [{version}] — {day}\n"]
    for kind in ORDER:
        if kind not in groups:
            continue
        lines.append(f"### {kind.capitalize()}\n")
        lines.extend(b if b.startswith("-") else f"- {b}" for b in groups[kind])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release")
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    groups = collect()
    if not groups:
        raise SystemExit("nothing queued in changelog.d/")
    if a.preview or not a.release:
        print(render(a.release or "UNRELEASED", groups))
        return
    section = render(a.release, groups)
    old = CHANGELOG.read_text() if CHANGELOG.exists() else HEAD
    body = old[len(HEAD):] if old.startswith(HEAD) else old.split("\n", 1)[-1]
    CHANGELOG.write_text(HEAD + "\n" + section + "\n" + body.lstrip("\n"))
    for f in QUEUE.glob("*.md"):
        if f.name != "README.md":
            f.unlink()
    print(f"wrote {a.release} to CHANGELOG.md and cleared {len(sum(groups.values(), []))} fragment(s)")


if __name__ == "__main__":
    main()
