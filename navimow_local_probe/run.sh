#!/usr/bin/with-contenv bashio
set -euo pipefail

readonly TCP_PORTS="21,22,23,53,80,443,554,1883,5683,8000,8080,8443,8883,9001"
readonly UDP_PORTS="53,123,161,5683,1900"

# shellcheck source=/usr/lib/navimow-local-probe.sh
source /usr/lib/navimow-local-probe.sh

target_ip="$(bashio::config 'target_ip')"
include_udp="$(bashio::config 'include_udp')"

if ! validate_private_ipv4 "$target_ip"; then
    bashio::log.fatal "target_ip must be one private IPv4 address (10/8, 172.16/12, or 192.168/16)."
    exit 2
fi

timestamp="$(date -u +'%Y%m%dT%H%M%SZ')"
report="/share/navimow-local-probe-${timestamp}.txt"

exec > >(tee -a "$report") 2>&1

echo "Navimow Local Probe 0.1.0"
echo "UTC timestamp: ${timestamp}"
echo "Target: ${target_ip}"
echo "Mode: read-only discovery; selected ports only"
echo

echo "== Route =="
ip route get "$target_ip" || true
echo

echo "== Reachability =="
ping -c 3 -W 2 "$target_ip" || true
echo

echo "== Neighbor table =="
ip neigh show "$target_ip" || true
echo

echo "== mDNS services resolving to the target =="
mdns_matches="$(
    (timeout 15 avahi-browse --all --resolve --terminate --parsable 2>/dev/null || true) \
        | grep -F ";${target_ip};" \
        || true
)"
if [[ -n "$mdns_matches" ]]; then
    printf '%s\n' "$mdns_matches"
else
    echo "No matching mDNS service observed."
fi
echo

echo "== Selected TCP services =="
nmap \
    -Pn \
    -n \
    -sT \
    -sV \
    --version-light \
    --script=banner,http-title,ssl-cert \
    -T3 \
    --max-retries 1 \
    --host-timeout 90s \
    --reason \
    -p "$TCP_PORTS" \
    "$target_ip" || true
echo

if bashio::var.true "$include_udp"; then
    echo "== Selected UDP services =="
    nmap \
        -Pn \
        -n \
        -sU \
        -sV \
        --version-light \
        -T3 \
        --max-retries 1 \
        --host-timeout 90s \
        --reason \
        -p "$UDP_PORTS" \
        "$target_ip" || true
    echo
else
    echo "== UDP scan =="
    echo "Skipped. Set include_udp to true for a second, limited scan."
    echo
fi

echo "Probe complete."
echo "Report saved as ${report}"
echo "Review the report before sharing it; it contains the mower's private IP and network identifiers."
