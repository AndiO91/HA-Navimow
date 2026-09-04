# Navimow Local Probe

This Home Assistant OS add-on performs a conservative, read-only LAN check of
one explicitly configured Navimow IP address. It does not log in to Navimow,
does not send mower commands, and does not scan the complete network.

The first run checks routing, reachability, the neighbor table, matching mDNS
services, and a small list of common TCP service ports. A limited UDP check is
available as an opt-in second step.

## Usage

1. Add `https://github.com/AndiHOK91/HA-Navimow` as a Home Assistant add-on
   repository.
2. Install **Navimow Local Probe**.
3. Enter the mower's private IPv4 address as `target_ip`.
4. Leave `include_udp` disabled for the first run.
5. Start the add-on once and open its log.
6. The same report is stored in `/share/navimow-local-probe-<timestamp>.txt`.

Review the file before sharing it. It contains the mower's private IP address,
route information, and possibly its MAC address or local service names.

## Interpretation

- `open` means the mower accepted a connection on that port.
- `closed` means the mower is reachable but no service listens there.
- `filtered` usually means a firewall or the device silently dropped the probe.
- No open ports does not rule out Bluetooth or an outbound-only cloud protocol.
