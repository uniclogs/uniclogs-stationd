# Uniclogs StationD

A power management Daemon for Uniclogs. Accept commands via UDP.

## Installation



## Usage

Command format: `````<Device> <Component> <State>`````

```
# turn on TX for VHF amplifier
vhf pa-power on

# turn off RX for UHF amplifier
uhf lna off

# turn on power for rotator accessory
rotator power on

# returns status for all devices for the L-Band amplifier
l-band status

# return status for polarization of VHF amplifier
vhf polarization status

# returns status for all components of every device
status
```

## License

[GPL 3.0](https://www.gnu.org/licenses/gpl-3.0.en.html)

