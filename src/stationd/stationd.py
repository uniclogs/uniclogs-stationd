"""Station daemon module for controlling RF amplifiers and accessories.

This module provides the main server functionality for the uniclogs-stationd
system, handling UDP commands for controlling RF amplifiers, accessories,
and other hardware components.
"""

import configparser
import logging
import socket
import threading
from pathlib import Path

import gpiod

from . import accessory as acc
from . import amplifier as amp
from .constants import IN, ON, OUT

# Module logger
logger = logging.getLogger(__name__)

# Config File
config = configparser.ConfigParser()
config.read('config.ini')

# UniClOGS UPB sensor
TEMP_PATH = Path('/sys/bus/i2c/drivers/adt7410/1-004a/hwmon/hwmon2/temp1_input')


class MaxPTTError(Exception):
    """Exception raised when maximum PTT connections are exceeded.

    Prevents exceeding the configured maximum number of simultaneous PTT
    connections.
    """


class ActivePTT:
    """Thread safe counter for tracking simultaneous PTT activations.

    At most PTT_MAX_COUNT PTT lines can be active at one time and this information needs to be
    shared across all accessories and amplifiers.
    """

    PTT_MAX_COUNT = 1

    def __init__(self) -> None:
        """Create a PTT counter initialized to 0."""
        self.count = 0
        self._lock = threading.Lock()

    def inc(self) -> None:
        with self._lock:
            if self.count >= self.PTT_MAX_COUNT:
                raise MaxPTTError
            self.count += 1

    def dec(self) -> None:
        with self._lock:
            self.count = max(self.count - 1, 0)


class StationD:
    """The main station daemon server.

    Manages UDP socket communications, hardware device instances, and command
    processing for the uniclogs-stationd system.
    """

    def __init__(self) -> None:
        """Initialize the station daemon.

        Sets up UDP socket, hardware device instances, shared state, and
        logging.
        """
        # UDP Socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((config['NETWORK']['udp_ip'], int(config['NETWORK']['udp_port'])))
        self.socket_lock = threading.Lock()
        # Shared ptt count
        self.active_ptt = ActivePTT()
        # Amplifiers
        self.vhf = amp.VHF(self.active_ptt)
        self.uhf = amp.UHF(self.active_ptt)
        self.l_band = amp.LBand(self.active_ptt)
        # Accessories
        self.vu_tx_relay = acc.VUTxRelay(self.active_ptt)
        self.satnogs_host = acc.SatnogsHost()
        self.radio_host = acc.RadioHost()
        self.rotator = acc.Rotator()
        self.sdr_b200 = acc.SDRB200()
        # Temperature sensor
        self.pi_cpu = TEMP_PATH
        # Logger
        logging.basicConfig(
            filename='activity.log',
            format='%(asctime)s\t%(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            encoding='utf-8',
            level=logging.DEBUG,
        )

    def shutdown_server(self) -> None:
        """Shut down the station daemon server."""
        logger.info('Closing connection...')
        self.sock.close()

    def command_handler(
        self, command: list[str], sock: socket.socket, client_address: tuple[str, int]
    ) -> None:
        """Handle incoming commands and route them to appropriate devices."""
        with self.socket_lock:
            try:
                device = command[0].replace('-', '_')

                if device in [
                    'vhf',
                    'uhf',
                    'l_band',
                    'vu_tx_relay',
                    'satnogs_host',
                    'radio_host',
                    'rotator',
                    'sdr_b200',
                ]:
                    message = command_parser(getattr(self, device), command)
                elif len(command) == 1 and command[0] == 'gettemp':
                    message = read_temp(self.pi_cpu)
                else:
                    message = 'FAIL: Invalid Command\n'
            except PTTConflictError:
                message = f'FAIL: {" ".join(command)} PTT Conflict\n'
            except amp.PTTCooldownError as e:
                message = f'WARNING: Please wait {e.seconds} seconds and try again\n'
            except amp.MollyGuardError as e:
                message = f'Re-enter the command within the next {e.seconds} seconds to proceed\n'
            except MaxPTTError:
                message = f'Fail: {" ".join(command)} Max PTT\n'
            except InvalidCommandError:
                message = 'FAIL: Invalid Command\n'
            except NoChangeError:
                message = f'WARNING: {" ".join(command)} No Change\n'

            sock.sendto(message.encode('utf-8'), client_address)
            logger.debug('ADDRESS: %s, %s', client_address, message.strip().replace('\n', ', '))

    def command_listener(self) -> None:
        """Listen for incoming UDP commands and spawn handler threads."""
        try:
            while True:
                try:
                    data, client_address = self.sock.recvfrom(1024)
                    command_data = data.decode().strip('\n').strip('\r').split()
                    c_thread = threading.Thread(
                        target=self.command_handler, args=(command_data, self.sock, client_address)
                    )
                    c_thread.daemon = True
                    c_thread.start()
                except OSError:
                    logger.exception('Socket error: %s')
        except KeyboardInterrupt:
            self.shutdown_server()


# Globals ----------------------------------------------------------------------


def command_parser(device: 'acc.Accessory | amp.TxAmplifier', command: list[str]) -> str:
    """Parse and execute commands for hardware devices."""
    if len(command) == 3:
        # Component Status command
        if command[2] == 'status':
            return device.component_status(command)
        # Component On/Off command
        fxn_name = f'{command[1].replace("-", "_")}_{command[2]}'
        try:
            fxn = getattr(device, fxn_name)
        except AttributeError as error:
            raise InvalidCommandError from error
        fxn()
        return f'SUCCESS: {" ".join(command)}\n'
    # Device Status Commands
    if len(command) == 2:
        return device.device_status(command)
    raise InvalidCommandError

def get_state(line) -> str:
    """Get the current state of a given GPIO pin."""
    value = line.get_value()
    return "ON" if value == 1 else "OFF"

# # FIXME
# def read_temp(path: Path) -> str:
#     """Read temperature from a persistent file handle and send response."""
#     with path.open('rb', buffering=0) as o:
#         temp = float(o.read()) / 1000
#     return f'temp: {temp!s}\n'

def get_status(line_request: gpiod.LineRequest, pin: int, command: list[str]) -> str:
    """Get a formatted status string for a GPIO pin."""
    try:
        value = line_request.get_value(pin)
        state = "ON" if value == gpiod.line.Value.ACTIVE else "OFF"
        return f'{command[0]} {command[1]} {state}\n'
    except Exception:
        logger.exception("Failed to get status for GPIO pin %s", pin)
        raise

def power_on(line_request: gpiod.LineRequest, pin: int) -> None:
    """Turn on power to a GPIO pin."""
    try:
        line_request.set_value(pin, gpiod.line.Value.ACTIVE)
        logger.info("Powered ON GPIO pin %s", pin)
    except Exception:
        logger.exception("Failed to power on GPIO pin %s", pin)
        raise

def power_off(line_request: gpiod.LineRequest, pin: int) -> None:
    """Turn off power to a GPIO pin."""
    try:
        line_request.set_value(pin, gpiod.line.Value.INACTIVE)
        logger.info("Powered OFF GPIO pin %s", pin)
    except Exception:
        logger.exception("Failed to power off GPIO pin %s", pin)
        raise

def assert_out(pin: int, chip_path: str) -> gpiod.LineRequest:
    """Ensure a GPIO pin is configured as an output pin."""
    try:
        chip = gpiod.Chip(chip_path)

        return chip.request_lines(
            consumer="stationd",
            config={pin: gpiod.LineSettings(direction=gpiod.line.Direction.OUTPUT)}
        )
    except Exception:
        logger.exception("Failed to assert GPIO pin %s on %s", pin, chip_path)
        raise


# Exceptions -------------------------------------------------------------------


class PTTConflictError(Exception):
    """Exception raised when PTT operation conflicts with current state.

    The requested PTT operation cannot be performed due to conflicting hardware
    states.
    """


class InvalidCommandError(Exception):
    """Exception raised for unrecognized or malformed commands."""


class NoChangeError(Exception):
    """Exception raised when a component is commanded to its current state.

    Not really an error but it does make control flow easier
    """
