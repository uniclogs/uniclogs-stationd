# ruff: noqa: T201

"""Entry point for the Station Daemon Package."""

import argparse

from . import stationd


def main() -> None:
    """Parse CLI args, load config, and start the daemon."""
    parser = argparse.ArgumentParser(description='Station daemon controller.')
    parser.add_argument(
        '--config',
        default=stationd.DEFAULT_CONFIG_PATH,
        help='Path to stationd.ini',
    )
    args = parser.parse_args()

    stationd.load_config(args.config)

    print('===============================')
    print('Station Daemon Power Management')
    print('===============================')

    sd = stationd.StationD()
    sd.command_listener()


if __name__ == '__main__':
    main()
