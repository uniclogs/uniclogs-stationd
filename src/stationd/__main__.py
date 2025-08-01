"""Entry point for the Station Daemon Package."""

from . import stationd

if __name__ == "__main__":
    print('===============================')
    print('Station Daemon Power Management')
    print('===============================')

    sd = stationd.StationD()
    sd.command_listener()
