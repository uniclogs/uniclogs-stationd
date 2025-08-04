# ruff: noqa: T201

"""Entry point for the Station Daemon Package."""

from . import stationd

print('===============================')
print('Station Daemon Power Management')
print('===============================')

sd = stationd.StationD()
sd.command_listener()
