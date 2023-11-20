#!/bin/bash

cd /sys/class/gpio

if ! [ $(ls | grep -c 'gpio[0-9]') -ge 24 ]; then
    for d in /sys/bus/i2c/drivers/pca953x/*/gpio/*; do
        count=$(<$d/ngpio)
        base=$(<$d/base)
        for (( i=$base; i<$((base+count)); i++ )); do
            echo $i >export 2>/dev/null
        done
    done
fi
exec grep ^ gpio???/value
