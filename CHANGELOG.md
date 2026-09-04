# Changelog

## [0.3.0](https://github.com/AndiHOK91/HA-Navimow/compare/NavimowPlus-v0.2.1...NavimowPlus-v0.3.0) (2026-09-04)


### Features

* add beta map support and local probe ([6874465](https://github.com/AndiHOK91/HA-Navimow/commit/687446558508b06fedf0531b5c5831990cbfb0c8))
* add diagnostics and active status polling ([519bed6](https://github.com/AndiHOK91/HA-Navimow/commit/519bed6259c2e928c211cbeadb77839d5bc85816))
* publish Navimow Plus 0.1.0 ([2b94d0a](https://github.com/AndiHOK91/HA-Navimow/commit/2b94d0a1a4d2cf1e7bb4bc9c1bf8f2d43fbdea0c))
* use Navimow SDK fork 0.1.3 ([3fea6fb](https://github.com/AndiHOK91/HA-Navimow/commit/3fea6fbdec1355c21d5e683ab122174a97164dff))


### Bug Fixes

* refresh mower state after commands ([006f4d3](https://github.com/AndiHOK91/HA-Navimow/commit/006f4d393017f9d2ccf70cce6e82c9f490f6611e))
* remove private app-cloud authentication ([20db7ad](https://github.com/AndiHOK91/HA-Navimow/commit/20db7ade8ed99f2bc96b7290266713a988afb65e))

## 0.2.1

- Switch the integration to the tested `0.1.3` release of our Navimow SDK fork
- Pin the SDK to an immutable Git commit for reproducible Home Assistant installs
- Retain attribution and links to the official upstream Navimow SDK

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
