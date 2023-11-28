#!/bin/sh

if [[ ${EUID} -ne 0 ]]; then
    echo " !!! This tool must be run as root"
    exit 1
fi

echo "This tool makes no effort to determine if any install has already taken place."
read -p "Press Enter to proceed. Ctrl-C to abort." RVAL

SERIAL=$(lsusb -vd 0403:6001 2>/dev/null | awk '$1=="iSerial"{print$3}')
if [ "${#SERIAL}" -eq 8 ]; then
    echo "Found a single FTDI UART interface and assumed it is the rotator controller."
    sed -i "s/xxxxxxxx/$SERIAL/" 99-serial.rules rotctld.service
else
    echo -e "Be sure to update the rotator FTDI serial numbers in these files:\n" \
	    "/etc/udev/rules.d/99-serial.rules\n" \
	    "/etc/systemd/system/rotctld.service"
fi

raspi-config nonint do_i2c 0
cat append-to-boot-config.txt >> /boot/firmware/config.txt
mkdir -p ~/bin
cp -t ~/bin stationc.sh gpio-scan.sh adc-scan.sh get-temp.sh park-rotator.sh
cp -t /etc/udev/rules.d/ 99-serial.rules

cp -t /etc/systemd/system/ rotctld.service stationd.service
systemctl enable now rotctld.service stationd.service

if [ ! -f ../config.ini ]; then
    cp config.ini-UPB ../config.ini
fi

echo -e "All done.  If you are not using standard UPD V2 GPIO numbering, be sure to edit\n" \
	"config.ini.  Please `sudo reboot` for the dtoverlays to take effect."
