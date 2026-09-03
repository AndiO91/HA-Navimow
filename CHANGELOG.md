# Changelog

## Unreleased

- Add a read-only Home Assistant OS add-on for targeted Navimow LAN discovery

## 0.2.0-beta.1

- Add optional map-cloud sign-in without storing the account password
- Cache map boundaries, zones, off-limit areas, channels, and charging station
- Subscribe to the official live-position MQTT topic
- Add X/Y position, heading, physical-zone, and map-data sensors
- Add an authenticated API compatible with the Navimower Map Card
- Keep the last map available when the private cloud is temporarily unreachable

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
