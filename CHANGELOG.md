# Changelog

## 0.2.0

- Add downloadable diagnostics for the integration and individual mower devices
- Include connection freshness, coordinator state, attributes, and recent events
- Recursively redact OAuth/MQTT secrets, identifiers, names, and position data
- Poll active states faster to recover MQTT transitions that the cloud omits
- Detect returning-to-docked transitions within about 30 seconds
- Add a read-only Home Assistant OS add-on for targeted Navimow LAN discovery

## 0.2.0-beta.3

- Use the SDK MQTT cache only for initial coordinator seeding
- Track MQTT state freshness separately from attributes and events
- Force an authoritative REST status refresh after mower commands
- Prefer a concurrent MQTT state push over an older REST response

## 0.2.0-beta.2

- Remove the private mobile-app cloud login and experimental map integration
- Use only the official Navimow OAuth flow and `navimow-sdk==0.1.2`
- Prevent the integration from creating a second mobile-app session

## 0.1.0

- Independent `navimow_plus` domain
- OAuth2 account setup and reauthentication
- MQTT state updates with five-minute HTTP fallback
- Start, pause, resume, and dock controls
- Battery, status, error, signal, source, and update-time sensors
- MQTT connectivity and problem diagnostics
- GPS device tracker when coordinates are supplied by Navimow
- German and English entity translations
- Exact `navimow-sdk==0.1.2` dependency pin
