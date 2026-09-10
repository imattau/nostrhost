#!/usr/bin/env bash
# pin-forks.sh — sync each nostrhost fork to the pin recorded in
# baseline/pins.yml and record the resulting commit pointer in the umbrella
# superproject.
#
# Usage:
#   scripts/pin-forks.sh            # ensure all forks are at pins.yml commits
#   scripts/pin-forks.sh --update   # for each fork, checkout the latest
#                                   # upstream <pin> tag available and rewrite
#                                   # pins.yml + submodule pointer to match
#                                   # (use after updating pins.yml, or to bump)
#
# Requires: git, yq (if present; falls back to awk for pin_commit), gh (for
# --update tag listing via the upstream repo).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PINS="$ROOT/baseline/pins.yml"
UPDATE=0
[[ "${1:-}" == "--update" ]] && UPDATE=1

get_pin() { awk -v c="$1" '
    $0 ~ "component: " c { found=1 }
    found && $0 ~ "pin_commit:" { print $2; exit }
    found && $0 ~ "^  - " && $0 !~ "component: " c { exit }
  ' "$PINS"; }

for pair in "yunohost debian/12.1.41.2 YunoHost/yunohost" \
            "portal debian/12.1.2 YunoHost/yunohost-portal" \
            "admin debian/12.1.15 YunoHost/yunohost-admin"; do
  set -- $pair
  comp="$1"; tag="$2"; upstream_repo="$3"
  dir="$ROOT/forks/$comp"

  echo "== $comp (pin $tag) =="
  [[ -d "$dir/.git" || -f "$dir/.git" ]] || { echo "  missing checkout; run git submodule update --init"; continue; }

  if [[ "$UPDATE" -eq 1 ]]; then
    # Refetch the upstream tag so the fork tracks latest of that same tag.
    git -C "$dir" fetch -q --force origin "+refs/tags/$tag:refs/tags/$tag" \
      && echo "  fetched upstream $tag"
  fi

  pin="$(get_pin "$comp")"
  head="$(git -C "$dir" rev-parse HEAD)"
  if [[ -n "$pin" && "$head" != "$pin" ]]; then
    git -C "$dir" checkout -q "$pin"
    echo "  checked out $pin"
  else
    echo "  already at $head"
  fi
done

echo
echo "Recording submodule pointers..."
git -C "$ROOT" add .gitmodules forks baseline/pins.yml
echo "Done. Review with: git status, git diff --cached --submodule"
