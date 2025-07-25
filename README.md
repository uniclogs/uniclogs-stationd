# Uniclogs StationD

A power management Daemon for Uniclogs. Accepts network commands via UDP.

## Installation

Install sysfs gpio library to program directory:

```sh
git clone -b 14-25-sysfs-permissions https://github.com/ctrlh/gpio.git
```

Install the project and its dependencies:

```sh
pip install -e ".[dev]"
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

## Testing

This project uses [pytest](https://docs.pytest.org/en/stable/) as it's testing
framework. Run tests with the following command:

```sh
pytest
```

A coverage report will be generated in the root of this project under
`htmlcov/` when tests are run. View the report by opening `htmlcov/index.html`
in a browser.
