#!/usr/bin/env bash

validate_private_ipv4() {
    local address="$1"
    local first second third fourth octet

    if [[ ! "$address" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
        return 1
    fi

    IFS=. read -r first second third fourth <<< "$address"
    for octet in "$first" "$second" "$third" "$fourth"; do
        if ((10#$octet > 255)); then
            return 1
        fi
    done

    if ((10#$first == 10)); then
        return 0
    fi
    if ((10#$first == 172 && 10#$second >= 16 && 10#$second <= 31)); then
        return 0
    fi
    if ((10#$first == 192 && 10#$second == 168)); then
        return 0
    fi
    return 1
}
