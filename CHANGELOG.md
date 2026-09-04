# Changelog

## Unreleased

- Add a read-only Home Assistant OS add-on for targeted Navimow LAN discovery

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
