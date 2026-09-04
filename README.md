# Navimow Plus for Home Assistant

An independent Home Assistant custom integration for Segway Navimow robotic
mowers. It is based on the official `navimow-sdk` and uses Navimow OAuth,
cloud MQTT updates, and a rate-limited HTTP fallback.

The integration uses the separate domain `navimow_plus`, so it can be tested
without replacing Home Assistant's `navimow` integration. Do not configure both
integrations against the same account for normal operation: two simultaneous
cloud/MQTT clients can make diagnosis unnecessarily difficult.

## Current support

| Function | State | Home Assistant entity |
|---|---|---|
| Start, pause, resume, dock | Stable | `lawn_mower` |
| Battery | Stable | `sensor` |
| Mower status | Stable | `sensor` |
| Current/last reported error | Stable where supplied by the cloud | `sensor`, `binary_sensor` |
| MQTT connection and data source | Diagnostic | `binary_sensor`, `sensor` |
| Signal strength | Diagnostic; payload-dependent | `sensor` (disabled by default) |
| GPS position | Payload-dependent | `device_tracker` |
| Zone discovery / zone mowing | Not exposed by SDK 0.1.2 | — |
| Schedule editing | Not exposed by SDK 0.1.2 | — |
| Blade height | Experimental SDK command; not exposed yet | — |

The `device_tracker` becomes available only after Navimow sends valid latitude
and longitude values. It can then be placed on Home Assistant's Map card. This
is a position marker, not the boundary or mowing-path map from the Navimow app.

## Requirements

- Home Assistant 2026.1.0 or newer
- A Navimow account that works in the official app
- Permanent internet access for cloud OAuth, REST, and MQTT

`navimow-sdk` is pinned to version `0.1.2` until newer releases have been tested
against the integration.

## Development installation

1. Copy `custom_components/navimow_plus` to the same path below the Home
   Assistant configuration directory.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration**.
4. Search for **Navimow Plus** and complete the Navimow login.

## Privacy and diagnostics

Access tokens, MQTT credentials, WebSocket paths, and raw MQTT payloads are not
written to normal integration logs. Diagnostic entities expose only connection
state, update source, and timestamp.

## Upstream projects

- [Official Navimow SDK](https://github.com/segwaynavimow/navimow-sdk)
- [Official Navimow Home Assistant integration](https://github.com/segwaynavimow/NavimowHA)

This project is not an official Segway Navimow product.

## HACS installation

1. In HACS, open **Integrations → Custom repositories**.
2. Add `https://github.com/AndiO91/HA-Navimow` as category **Integration**.
3. Install **Navimow Plus** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration** and select
   **Navimow Plus**.

Report problems in the [issue tracker](https://github.com/AndiO91/HA-Navimow/issues).

## Experimental local discovery

The repository also contains the **Navimow Local Probe** Home Assistant OS
add-on. It performs a read-only check of one configured private IP address and
saves its report in `/share`. This can show whether a mower exposes a local
service; it does not yet provide local control.

Add this repository to the Home Assistant add-on store to install the probe:
`https://github.com/AndiO91/HA-Navimow`.
