"""Entry point for the Station Daemon Package."""

from . import stationd

if __name__ == "__main__":
    print('===============================')  # noqa: T201
    print('Station Daemon Power Management')  # noqa: T201
    print('===============================')  # noqa: T201

    sd = stationd.StationD()
    sd.command_listener()
