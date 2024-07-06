#!/bin/bash

help() {
    echo "Available commands: gettemp, l-band pa-power on, l-band rf-ptt on, uhf polarization left, vhf status, rotator power on, vu-tx-relay power on ...\n"
}
host=127.0.0.1

case "$1" in
    "") exec nc.openbsd -uw1 $host 5005 ;;
    "help") help ;;
    "status") set -- "gettemp" "vhf status" "uhf status" "l-band status" "vu-tx-relay status" "rotator status" "radio-host status" "sbr-b200 status" "satnogs-host status" ;&
    *)
	while [ -n "$1" ]; do
	    echo "$1"
	    shift
	    sleep 0.1
	done | nc.openbsd -uw1 $host 5005
    ;;
esac
