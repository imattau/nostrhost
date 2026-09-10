#!/usr/bin/env bash
# Deploy the P2 ACME spike on the VM. Run from this directory on the VM.
#
# Prereqs:
#   - pebble binary already at /usr/local/bin/pebble (build-pebble.sh + scp)
#   - the P0/P1 spike installed: /opt/caddy-p0/caddy and the active
#     /etc/caddy-p0/Caddyfile
#
# This installs the Pebble CA, its systemd unit and trust-store entry, adds
# loopback hosts entries, then swaps the active Caddyfile to the Pebble-ACME
# variant (keeping the P1 file as Caddyfile.p1) and reloads Caddy.
set -euo pipefail

CADDY=/etc/caddy-p0
HERE="$(cd "$(dirname "$0")" && pwd)"

# Pebble CA + endpoint cert + system trust store entry
"$HERE/setup-certs.sh" /etc/pebble
install -m 0644 "$HERE/pebble-config.json" /etc/pebble/pebble-config.json
install -m 0644 "$HERE/pebble.service" /etc/systemd/system/pebble.service

# hosts entries so Pebble's VA resolves the test names to loopback
for d in nostrhost.test yunohost.org; do
  grep -q "127.0.0.1	$d" /etc/hosts || echo "127.0.0.1	$d" >> /etc/hosts
done

systemctl daemon-reload
systemctl enable --now pebble
sleep 1
curl -sk https://127.0.0.1:14000/dir >/dev/null && echo "pebble ACME directory reachable"

# swap the active Caddyfile to the ACME variant and reload
[ -f "$CADDY/Caddyfile.p1" ] || cp "$CADDY/Caddyfile" "$CADDY/Caddyfile.p1"
install -m 0644 "$HERE/caddyfile.acme-test" "$CADDY/Caddyfile"
/opt/caddy-p0/caddy adapt --config "$CADDY/Caddyfile" >/dev/null
/opt/caddy-p0/caddy reload --config "$CADDY/Caddyfile"
echo "Caddy reloaded with ACME config; trigger a handshake to force issuance:"
echo "  curl -k --resolve nostrhost.test:8443:127.0.0.1 https://nostrhost.test:8443/"