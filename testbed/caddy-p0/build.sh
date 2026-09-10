#!/usr/bin/env bash
# P0 spike: build Caddy with the layer4 module (caddy-l4).
#
# Requires Go >= 1.22 and network access. Outputs ./caddy in the CWD.
# GOFLAGS=-buildvcs=false avoids Go's VCS stamping failing in the xcaddy
# temp build dir.
set -euo pipefail

go install github.com/caddyserver/xcaddy/cmd/xcaddy@latest

export GOFLAGS=-buildvcs=false
"$(go env GOPATH)/bin/xcaddy" build --with github.com/mholt/caddy-l4

./caddy version
./caddy list-modules | grep -i '^layer4'
