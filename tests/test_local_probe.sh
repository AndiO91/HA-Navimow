#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/../navimow_local_probe/lib.sh"

for address in 10.0.0.1 172.16.0.1 172.31.255.254 192.168.1.42; do
    validate_private_ipv4 "$address"
done

for address in "" example.local 8.8.8.8 172.15.0.1 172.32.0.1 192.169.1.1 999.1.1.1; do
    if validate_private_ipv4 "$address"; then
        echo "Unexpectedly accepted: $address" >&2
        exit 1
    fi
done
