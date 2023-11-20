#!/bin/sh

v=$(cat /sys/bus/i2c/drivers/adt7410/1-004a/hwmon/hwmon?/temp1_input)

# set up for magnitude adjustment
math="$((v))/1000"

# bash only does integer math, so use bc
degc=$(echo "scale=3; $math" | bc)

echo "$degc C"
