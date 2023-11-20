#!/bin/sh

cd /sys/bus/i2c/drivers/ads1015/*/iio:device?/
exec grep ^ in_voltage?_raw
