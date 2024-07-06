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


Command Examples:
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

# get temperature of board
gettemp
```

Supported Commands:
```
<vhf|uhf> <pa-power|rf-ptt|lna> <on|off|status>

<vhf|uhf> polarization <left|right|status>

l-band <pa-power|rf-ptt> <on|off|status>

<rx-swap|satnogs-host|radio-host|sdr-b200|rotator> power <on|off|status>

<vhf|uhf|l-band|rx-swap|satnogs-host|radio-host|sdr-b200|rotator> status

gettemp
```


## License

[GPL 3.0](https://www.gnu.org/licenses/gpl-3.0.en.html)

