# Navimow Plus for Home Assistant

An independent Home Assistant custom integration for Segway Navimow robotic
mowers.

> **Built with our [Navimow SDK fork](https://github.com/AndiHOK91/navimow-sdk),**
> based on the official [Navimow Python SDK](https://github.com/segwaynavimow/navimow-sdk).
> The integration currently installs version `0.1.3` and uses it for
> device discovery, REST status requests, MQTT updates, and mower commands.

Navimow Plus adds the Home Assistant-specific OAuth setup, coordinator,
entities, command confirmation, diagnostics, and update fallback around that
SDK. It is an independent integration, not a fork of the SDK.

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
| Zone discovery / zone mowing | Not exposed by SDK 0.1.3 | — |
| Schedule editing | Not exposed by SDK 0.1.3 | — |
| Blade height | Experimental SDK command; not exposed yet | — |

The `device_tracker` becomes available only after Navimow sends valid latitude
and longitude values. It can then be placed on Home Assistant's Map card. This
is a position marker, not the boundary or mowing-path map from the Navimow app.

## Requirements

- Home Assistant 2026.1.0 or newer
- A Navimow account that works in the official app
- Permanent internet access for cloud OAuth, REST, and MQTT

`navimow-sdk` is pinned to the exact, tested `0.1.3` commit of our fork. Home
Assistant therefore installs the same immutable source revision on every system.

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

Home Assistant can download a diagnostic file for the integration or an
individual mower from **Settings → Devices & services → Navimow Plus → three-dot
menu → Download diagnostics**. It contains sanitized connection freshness,
coordinator state, attributes, and the latest event. OAuth/MQTT credentials,
device identifiers, names, serial numbers, and position data are recursively
redacted before the file leaves Home Assistant.

## Upstream projects

- [Our Navimow SDK fork](https://github.com/AndiHOK91/navimow-sdk) — tested
  core library used by this integration (`0.1.3`, GPL-3.0-only)
- [Official Navimow Python SDK](https://github.com/segwaynavimow/navimow-sdk) —
  upstream project on which our fork is based
- [Official Navimow Home Assistant integration](https://github.com/segwaynavimow/NavimowHA)

See [Third-party notices](THIRD_PARTY_NOTICES.md) for dependency and license
details.

This project is not an official Segway Navimow product.

## HACS installation

1. In HACS, open **Integrations → Custom repositories**.
2. Add `https://github.com/AndiHOK91/HA-Navimow` as category **Integration**.
3. Install **Navimow Plus** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration** and select
   **Navimow Plus**.

Report problems in the [issue tracker](https://github.com/AndiHOK91/HA-Navimow/issues).

## Experimental local discovery

The repository also contains the **Navimow Local Probe** Home Assistant OS
add-on. It performs a read-only check of one configured private IP address and
saves its report in `/share`. This can show whether a mower exposes a local
service; it does not yet provide local control.

Add this repository to the Home Assistant add-on store to install the probe:
`https://github.com/AndiHOK91/HA-Navimow`.
