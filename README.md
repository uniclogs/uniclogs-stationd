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

### Creating a Release

1.  Navigate to this project's "Releases" page
2.  Click "Draft a new release"
3.  Click "Tag: Select tag" and click on the "Create new tag" button
4.  Add a tag following the [SemVer](https://semver.org/) standard
    -   e.g. `v1.2.3`
5.  Ensure that Target button is pointing at the `main` branch
6.  Add all necessary details about the release under "Release notes"
7.  Once everything looks good, click the "Publish release" button

Step 7 will trigger the `pypi.yml` workflow and the new release will be
available on pypi.org.

### Post-Release

Once a new release has been created and is available on pypi.org, smoke test
the release to ensure it runs as expected.

```sh
pip install your-package==X.Y.Z
```
