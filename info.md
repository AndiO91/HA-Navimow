# Navimow Plus

Navimow Plus controls and monitors Segway Navimow robotic mowers through the
Navimow cloud.

It is built with the official
[Navimow Python SDK](https://github.com/segwaynavimow/navimow-sdk), currently
pinned to `navimow-sdk==0.1.2`. The SDK provides device discovery, REST status,
MQTT updates, and mower commands; Navimow Plus supplies the Home Assistant
integration around it. This repository is not a fork of the SDK.

Included in the first release:

- Start, pause, resume, and return to dock
- Battery and mower status
- Error and connection diagnostics
- MQTT updates with rate-limited HTTP fallback
- A Home Assistant map marker when the mower supplies GPS coordinates

Zone mowing, Navimow app map images, schedule editing, and blade-height control
are not shown until the SDK offers verified support for them.

[Documentation](https://github.com/AndiHOK91/HA-Navimow) ·
[Navimow SDK](https://github.com/segwaynavimow/navimow-sdk) ·
[Issues](https://github.com/AndiHOK91/HA-Navimow/issues)
