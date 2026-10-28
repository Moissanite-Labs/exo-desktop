#!/bin/sh
set -eu
cd "$(dirname "$0")"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
swiftc Sources/ExoDesktop/ExoWebLauncher.swift Tests/main.swift -o "$tmp/test-launcher"
"$tmp/test-launcher"
