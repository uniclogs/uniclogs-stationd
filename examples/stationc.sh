#!/bin/sh

help() {
    echo "Available commands: gettemp, l-band pa-power on, l-band rf-ptt on, uhf polarization left, vhf status, rotator power on, vu-tx-relay power on ...\n"
}
host=127.0.0.1

if [ -n "$1" ]; then
    if [ "$1" = 'help' ]; then
        help
        exit 0
    fi
    while [ -n "$1" ]; do
        echo "$1"
        shift
        sleep 0.1
    done | nc.openbsd -uw1 $host 5005
else
    exec nc.openbsd -uw1 $host 5005
fi
