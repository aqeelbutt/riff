#!/usr/bin/env bash
# The gate before tagging: version literals agree, tests pass, the app builds, nothing uncommitted.
#   scripts/release_check.sh 1.0.0
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"; export PATH="$HOME/.local/bin:$PATH"
V="${1:?usage: release_check.sh X.Y.Z}"; fail=0
say(){ printf "%-34s %s\n" "$1" "$2"; }
check(){ [[ "$2" == "$3" ]] && say "$1" "ok ($2)" || { say "$1" "MISMATCH: $2 != $3"; fail=1; }; }
check "root package.json"    "$(node -p "require('./package.json').version" 2>/dev/null)" "$V"
check "apps/web/package.json" "$(node -p "require('./apps/web/package.json').version" 2>/dev/null)" "$V"
check "backend APP_VERSION"  "$(grep -oE '^APP_VERSION = "[^"]+"' apps/backend/app/api/health.py | cut -d'"' -f2)" "$V"
check "backend pyproject"    "$(grep -oE '^version = "[^"]+"' apps/backend/pyproject.toml | cut -d'"' -f2)" "$V"
grep -q "## \[$V\]" CHANGELOG.md 2>/dev/null && say "CHANGELOG section" "ok" || { say "CHANGELOG section" "MISSING — run scripts/assemble_changelog.py --release $V"; fail=1; }
n=$(ls changelog.d/*.md 2>/dev/null | grep -v README | wc -l | tr -d ' ')
[[ "$n" == "0" ]] && say "changelog.d queue" "empty (ok)" || say "changelog.d queue" "$n fragment(s) left for the NEXT release"
(cd apps/backend && ./run_tests.sh >/tmp/riff_be.log 2>&1) && say "backend tests" "$(tail -1 /tmp/riff_be.log | tr -s ' ')" || { say "backend tests" "FAILED (see /tmp/riff_be.log)"; fail=1; }
(cd apps/web && pnpm test >/tmp/riff_fe.log 2>&1) && say "web tests" "$(grep -E '^ +Tests ' /tmp/riff_fe.log | tr -s ' ')" || { say "web tests" "FAILED (see /tmp/riff_fe.log)"; fail=1; }
(cd apps/web && NEXT_DIST_DIR=.next-build pnpm build >/tmp/riff_build.log 2>&1) && say "web build" "ok" || { say "web build" "FAILED (see /tmp/riff_build.log)"; fail=1; }
[[ -z "$(git status --porcelain)" ]] && say "working tree" "clean" || { say "working tree" "DIRTY — commit first"; fail=1; }
echo; [[ $fail == 0 ]] && echo "READY to tag v$V" || { echo "NOT ready"; exit 1; }
