#!/usr/bin/env bash
# Build Pebble (Let's Encrypt's ACME test CA) for the P2 spike.
#
# Run on the host (the VM has no Go toolchain), then copy ./pebble to the VM:
#   scp ./pebble root@<vm>:/usr/local/bin/pebble
set -euo pipefail

export GOFLAGS=-buildvcs=false
# v2.10.1 pinned: requires go >= 1.24 (go install auto-downloads a toolchain).
go install github.com/letsencrypt/pebble/v2/cmd/pebble@v2.10.1
install -m 0755 "$(go env GOPATH)/bin/pebble" ./pebble
./pebble -version