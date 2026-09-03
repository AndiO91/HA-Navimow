# Navimow Local Probe

Use this add-on to determine whether a Navimow mower exposes services directly
on the local network.

## Configuration

### `target_ip`

Required. Enter the mower's private IPv4 address as shown by your router, for
example `192.168.1.42`. Public addresses and host names are rejected.

### `include_udp`

Leave this disabled for the first run. Enable it only for a second run if the
TCP report contains no open services. The UDP scan is limited to ports 53, 123,
161, 5683, and 1900.

## Running the probe

1. Save the add-on configuration.
2. Start the add-on.
3. Open **Log** and wait for `Probe complete`.
4. Open the `share` folder with File editor, Samba, or Studio Code Server.
5. Locate `navimow-local-probe-<timestamp>.txt`.

The add-on stops after every run. It does not need to remain active.

## Privacy

The report stays on your Home Assistant system. It may contain private IP and
MAC addresses, local routes, and service names. Review or redact those values
before posting the report publicly.

The add-on does not request Navimow credentials, contact the Navimow cloud, or
send mower-control commands.
