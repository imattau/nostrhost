# forks.sh — shared fork pin list and pins.yml lookup helper, sourced by
# scripts/pin-forks.sh and scripts/verify-clean.sh. Not directly executable.

FORK_PAIRS=(
  "yunohost debian/12.1.41.2 YunoHost/yunohost"
  "portal debian/12.1.2 YunoHost/yunohost-portal"
  "admin debian/12.1.15 YunoHost/yunohost-admin"
  "installer main YunoHost/custom-debian-iso"
)

# get_pin <component> -> prints the pin_commit recorded for <component> in
# $PINS (baseline/pins.yml). Requires the caller to have set PINS.
get_pin() {
  awk -v c="$1" '
    $0 ~ "component: " c { found=1 }
    found && $0 ~ "pin_commit:" { print $2; exit }
    found && $0 ~ "^  - " && $0 !~ "component: " c { exit }
  ' "$PINS"
}
