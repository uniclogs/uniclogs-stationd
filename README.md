# Uniclogs StationD

A power management Daemon for Uniclogs. Accepts network commands via UDP.

## Installation

StationD requires python 3.10 or later

Install sysfs gpio library to program directory:
```
$ git clone -b 14-25-sysfs-permissions https://github.com/ctrlh/gpio.git
```

## Usage

Set desired IP address and port number at top of stationd.py:
```
UDP_IP = '127.0.0.1'
UDP_PORT = 5005
```

To run the program: ```$ python3 stationd.py```

Example UDP command using Netcat:
```
echo "vhf polarization status" | nc -u -w 1 127.0.0.1 5005
```

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

# returns status for all components of UHF amplifier
uhf status
```

Supported Commands:
```
# VHF Commands

vhf pa-power on
vhf pa-power off
vhf pa-power status
vhf rf-ptt on
vhf rf-ptt off
vhf rf-ptt status
vhf lna on
vhf lna off
vhf lna status
vhf polarization left
vhf polarization right
vhf polarization status
vhf status

# UHF Commands

uhf pa-power on
uhf pa-power off
uhf pa-power status
uhf rf-ptt on
uhf rf-ptt off
uhf rf-ptt status
uhf lna on
uhf lna off
uhf lna status
uhf polarization left
uhf polarization right
uhf polarization status
uhf status

# L-band Commands

l-band pa-power on
l-band pa-power off
l-band pa-power status
l-band rf-ptt on
l-band rf-ptt off
l-band rf-ptt status
l-band status

# RX-Swap Commands

rx-swap power on
rx-swap power off
rx-swap power status
rx-swap status

# SBC Satnogs Commands

sbc-satnogs power on
sbc-satnogs power off
sbc-satnogs power status
sbc-satnogs status

# SDR-Lime Commands

sdr-lime power on
sdr-lime power off
sdr-lime power status
sdr-lime status

# Rotator Commands

rotator power on
rotator power off
rotator power status
rotator status
```


## License

[GPL 3.0](https://www.gnu.org/licenses/gpl-3.0.en.html)

