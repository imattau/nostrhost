#!/usr/bin/env bash
# verify-clean.sh — assert every nostrhost fork is source-identical to the
# upstream pin recorded in baseline/pins.yml.
#
# The primary invariant: each fork's HEAD equals the recorded pin_commit
# (the upstream "debian/<version>" tag commit at pin time). Tag comparisons
# are consistency checks and are skipped gracefully when tags are not
# available (e.g. a tagless CI checkout).
#
# Exits non-zero if any fork:
#   - is missing
#   - is dirty (uncommitted changes vs its HEAD)
#   - is NOT at the pinned commit recorded in pins.yml / the superproject
#   - has committed local changes relative to the pinned upstream tag
#
# Usage: scripts/verify-clean.sh [--strict]
#   --strict  additionally fail if the pinned tag has moved upstream away
#             from the recorded pin_commit (i.e. the recorded pin is stale).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PINS="$ROOT/baseline/pins.yml"
STRICT=0
[[ "${1:-}" == "--strict" ]] && STRICT=1

# Fallback awk extraction of pin_commit when yq is unavailable.
get_pin() {
  local component="$1"
  awk -v c="$component" '
    $0 ~ "component: " c { found=1 }
    found && $0 ~ "pin_commit:" { print $2; exit }
    found && $0 ~ "^  - " && $0 !~ "component: " c { exit }
  ' "$PINS"
}

# tagref <comp> <tag> <upstream_repo> -> resolves the CURRENT upstream tag
# commit into refs/nostrhost/upstream-<comp>-<tag>; prints nothing. Best
# effort: fails silently if upstream is unreachable.
fetch_upstream_tag() {
  local comp="$1" tag="$2" upstream_repo="$3"
  git -C "$ROOT/forks/$comp" fetch -q --force \
    "https://github.com/$upstream_repo.git" \
    "+refs/tags/$tag:refs/nostrhost/upstream-$comp-$tag" 2>/dev/null || return 1
}

# is_derivative <component> -> prints "true" when pins.yml marks the fork
# as diverged onto its own derivative branch.
is_derivative() {
  local component="$1"
  awk -v c="$component" '
    $0 ~ "component: " c { found=1 }
    found && $0 ~ "derivative:" { print $2; exit }
    found && $0 ~ "^  - " && $0 !~ "component: " c { exit }
  ' "$PINS"
}

fail=0
for pair in "yunohost debian/12.1.41.2 YunoHost/yunohost" \
            "portal debian/12.1.2 YunoHost/yunohost-portal" \
            "admin debian/12.1.15 YunoHost/yunohost-admin"; do
  set -- $pair
  comp="$1"; tag="$2"; upstream_repo="$3"
  dir="$ROOT/forks/$comp"
  comp_fail=0
  deriv="$(is_derivative "$comp")"

  echo "== $comp (pin $tag${deriv:+, derivative branch}) =="
  if ! git -C "$dir" rev-parse --git-dir >/dev/null 2>&1; then
    echo "  FAIL: missing submodule checkout at forks/$comp (run: git submodule update --init)"
    fail=1; continue
  fi

  # 1. dirty?
  if ! git -C "$dir" diff --quiet -- ; then
    echo "  FAIL: working tree has uncommitted changes"
    comp_fail=1
  fi

  # 2. at the recorded pin_commit?
  pin="$(get_pin "$comp")"
  head="$(git -C "$dir" rev-parse HEAD)"
  if [[ -z "$pin" ]]; then
    echo "  FAIL: no pin_commit recorded in baseline/pins.yml for $comp"
    comp_fail=1
  elif [[ "$head" != "$pin" ]]; then
    echo "  FAIL: HEAD $head != pinned $pin"
    comp_fail=1
  fi

  # 3/4. Source-identity checks vs the upstream pin apply only to
  #      source-identical forks; a derivative fork is expected to have
  #      diverged (its pin_commit is its own branch tip).
  if [[ "$deriv" != "true" ]]; then
    taghead=""
    if git -C "$dir" rev-parse --verify -q "refs/tags/$tag^{commit}" >/dev/null; then
      taghead="$(git -C "$dir" rev-parse "refs/tags/$tag^{commit}")"
    elif fetch_upstream_tag "$comp" "$tag" "$upstream_repo"; then
      taghead="$(git -C "$dir" rev-parse "refs/nostrhost/upstream-$comp-$tag^{commit}")"
    fi

    if [[ -n "$taghead" ]]; then
      if [[ "$taghead" != "$pin" ]]; then
        echo "  WARN: recorded pin $pin differs from current $tag ($taghead)"
        [[ "$STRICT" -eq 1 ]] && comp_fail=1
      elif [[ "$head" != "$taghead" ]]; then
        echo "  FAIL: committed changes beyond the $tag upstream tag"
        comp_fail=1
      fi
    else
      echo "  note: $tag not resolvable here; relying on HEAD==pin check"
    fi

    git -C "$dir" update-ref -d "refs/nostrhost/upstream-$comp-$tag" 2>/dev/null || true
  fi

  if [[ $comp_fail -eq 0 ]]; then
    if [[ "$deriv" == "true" ]]; then
      echo "  ok: on derivative branch at $head (expected divergence)"
    else
      echo "  ok: source-identical at $head"
    fi
  else
    fail=1
  fi
done

echo
if [[ $fail -eq 0 ]]; then
  echo "verify-clean: PASS — all forks verified (derivative branches at their pins; source-identical forks match upstream)"
else
  echo "verify-clean: FAIL — see above"
  exit 1
fi