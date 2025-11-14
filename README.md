# Uniclogs StationD

A power management Daemon for Uniclogs. Accepts network commands via UDP.

## Installation

### For Development (Container)

These instructions assume you have Podman installed and configured.

1.  Build and run the container:

    ```sh
    podman compose up -d
    ```

2.  Drop into the container:

    ```sh
    podman compose exec stationd bash
    ```

3.  Install dependencies (inside the container):

    ```sh
    pip install -e .[dev]
    ```

### For Raspberry Pi (Hardware)

1.  Install Python dependencies:

    ```sh
    pip install -e .
    ```

2.  Modify the config.ini file at the root of the project to suite your needs.

3.  Run the daemon:

    ```sh
    python -m stationd
    ```

## Usage

### Example UDP command using Netcat

```
echo "vhf polarization status" | nc -u -w 1 127.0.0.1 5005
```

### Example StationD Commands

```
# turn on TX for VHF amplifier
vhf pa-power on

# turn off RX for UHF amplifier
uhf lna off

# turn on power for rotator accessory
rotator power on

# returns status for all devices for the L-Band amplifier
l-band status

# return status for polarization of VHF amplifier
vhf polarization status

# returns status for all components of UHF amplifier
uhf status

# get temperature of board
gettemp
```

### Supported Commands

```
<vhf|uhf> <pa-power|rf-ptt|lna> <on|off|status>

<vhf|uhf> polarization <left|right|status>

l-band <pa-power|rf-ptt> <on|off|status>

<rx-swap|satnogs-host|radio-host|sdr-b200|rotator> power <on|off|status>

<vhf|uhf|l-band|rx-swap|satnogs-host|radio-host|sdr-b200|rotator> status

gettemp
```

## Testing

This project uses [pytest](https://docs.pytest.org/en/stable/) as it's testing
framework. Run tests with the following command:

```sh
pytest
```

A coverage report will be generated in the root of this project under
`htmlcov/` when tests are run. View the report by opening `htmlcov/index.html`
in a browser.

## Release Process

Releases are managed through an automated workflow using Github Actions. The
automation is triggered when a release is published on Github.

<!-- ### Manual

1.  Pre-release Checks
    1.  Ensure all tests are passing
    2.  Verify the `main` git branch is up to date
    3.  Review changes since the last release (git tag)
        1.  Choose a version number to bump to (Use SemVer `<major.minor.patch>`)
2.  Version Update
    1.  Bump version number in `pyproject.toml` to the version number chosen in Pre-release Checks steps
    2.  Commit these changes on the `main` branch. (`git commit -m "Bump version to X.Y.Z"`)
3.  Tag Release
    1.  Tag the release: `git tag -a vX.Y.Z -m "Release version X.Y.Z"`
    2.  Push version updates and tags: `git push main && git push --tags`
4.  Build Distribution
    1.  Upgrade to latest version of build: `python3 -m pip install --upgrade build`
    2.  Install or upgrade to latest version of twine: `python3 -m pip install --upgrade twine`
    3.  Build the package: `python3 -m build`
5.  Upload to Pypi
    1.  Push the package to PyPi repository: `python3 -m twine upload dist/*`
6.  Create Release in Github
    1.  Go to your GitHub repo's "Releases" page
    2.  Click "Draft a new release"
    3.  Select the tag you just pushed
    4.  Add release notes (can copy from CHANGELOG.md)
    5.  Publish the release
7.  Smoke-test
    1.  Test the package installation after uploading: `pip install your-package==X.Y.Z` -->
