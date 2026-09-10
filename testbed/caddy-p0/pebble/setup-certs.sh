#!/usr/bin/env bash
# Generate the Pebble ACME test CA and the TLS cert Pebble's HTTPS endpoint
# (https://127.0.0.1:14000) presents -- self-contained with openssl, no minica.
# The CA is also installed into the system trust store so Caddy (Go TLS, system
# roots) accepts the endpoint. For a test VM only; never on a real host.
set -euo pipefail

D="${1:-/etc/pebble}"
mkdir -p "$D/tls"

umask 077
openssl genrsa -out "$D/ca.key" 2048
openssl req -x509 -new -key "$D/ca.key" -sha256 -days 3650 -subj "/CN=Pebble Test Root CA" -out "$D/ca.pem"
openssl genrsa -out "$D/tls/key.pem" 2048
openssl req -new -key "$D/tls/key.pem" -subj "/CN=pebble" -out /tmp/pebble.csr
printf "subjectAltName=IP:127.0.0.1,DNS:localhost,DNS:pebble\nbasicConstraints=CA:FALSE\n" > /tmp/pebble.ext
openssl x509 -req -in /tmp/pebble.csr -CA "$D/ca.pem" -CAkey "$D/ca.key" -CAcreateserial -days 3650 -sha256 -extfile /tmp/pebble.ext -out "$D/tls/cert.pem"
rm -f /tmp/pebble.csr /tmp/pebble.ext

install -m 0644 "$D/ca.pem" /usr/local/share/ca-certificates/pebble-test-ca.crt
update-ca-certificates