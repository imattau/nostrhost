#!/usr/bin/env bash
# verify-clean.sh — assert every nostrhost fork is source-identical to the
# upstream pin recorded in baseline/pins.yml.
#
# Exits non-zero if any fork:
#   - is missing
#   - is dirty (uncommitted changes vs its HEAD)
#   - is NOT at the pinned commit recorded in pins.yml / the superproject
#   - has diverged from the pinned upstream tag (committed local changes)
#
# Usage: scripts/verify-clean.sh [--strict]
#   --strict  additionally fail if a fork's pinned tag differs from the
#             current upstream tag of the same name (i.e. the fork is stale
#             relative to upstream, even if the submodule pointer is intact).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PINS="$ROOT/baseline/pins.yml"
STRICT=0
[[ "${1:-}" == "--strict" ]] && STRICT=1

have_yq() { command -v yq >/dev/null 2>&1; }

# yq may not be installed; fall back to a tiny awk extraction of pin_commit.
get_pin() {
  local component="$1"
  awk -v c="$component" '
    $0 ~ "component: " c { found=1 }
    found && $0 ~ "pin_commit:" { print $2; exit }
    found && $0 ~ "^  - " && $0 !~ "component: " c { exit }
  ' "$PINS"
}

fail=0
for pair in "yunohost debian/12.1.41.2 YunoHost/yunohost" \
            "portal debian/12.1.2 YunoHost/yunohost-portal" \
            "admin debian/12.1.15 YunoHost/yunohost-admin" \
            "ssowat debian/12.1.1 YunoHost/SSOwat"; do
  set -- $pair
  comp="$1"; tag="$2"; upstream_repo="$3"
  dir="$ROOT/forks/$comp"

  echo "== $comp ($tag) =="
  if ! git -C "$dir" rev-parse --git-dir >/dev/null 2>&1; then
    echo "  FAIL: missing submodule checkout at forks/$comp (run: git submodule update --init)"
    fail=1; continue
  fi

  # 1. dirty?
  if ! git -C "$dir" diff --quiet -- ; then
    echo "  FAIL: working tree has uncommitted changes"
    fail=1
  fi

  # 2. at the pinned commit?
  pin="$(get_pin "$comp")"
  head="$(git -C "$dir" rev-parse HEAD)"
  if [[ -n "$pin" && "$head" != "$pin" ]]; then
    echo "  FAIL: HEAD $head != pinned $pin"
    fail=1
  fi

  # 3. committed local changes vs the upstream tag (source-identical check)?
  #    The fork should be exactly the upstream tag tree. Compare against the
  #    upstream repo object by refspec; fall back to a local tag comparison.
  if ! git -C "$dir" rev-parse --verify -q "refs/tags/$tag" >/dev/null; then
    echo "  FAIL: tag $tag not present locally"
    fail=1
  else
    taghead="$(git -C "$dir" rev-parse "refs/tags/$tag^{commit}")"
    if [[ "$head" != "$taghead" ]]; then
      echo "  FAIL: committed changes beyond the $tag upstream tag"
      fail=1
    fi
  fi

  # 4. strict: is the fork's tag stale vs upstream?
  if [[ "$STRICT" -eq 1 ]]; then
    # fetch the upstream tag (not the fork's origin) into a temp ref and compare
    if git -C "$dir" fetch -q --force "https://github.com/$upstream_repo.git" \
          "+refs/tags/$tag:refs/nostrhost/upstream-$tag" 2>/dev/null; then
      uph="$(git -C "$dir" rev-parse "refs/nostrhost/upstream-$tag^{commit}" 2>/dev/null || true)"
      if [[ -n "$uph" && "$uph" != "$taghead" ]]; then
        echo "  WARN: fork tag $tag is stale vs upstream ($taghead -> $uph)"
        [[ "$STRICT" -eq 1 ]] && fail=1
      fi
      git -C "$dir" update-ref -d "refs/nostrhost/upstream-$tag" 2>/dev/null || true
    fi
  fi

  [[ $fail -eq 0 ]] && echo "  ok: source-identical at $head"
done

echo
if [[ $fail -eq 0 ]]; then
  echo "verify-clean: PASS — all forks source-identical to pins"
else
  echo "verify-clean: FAIL — see above"
  exit 1
fi
