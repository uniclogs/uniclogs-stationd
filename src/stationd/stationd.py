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
    '''Thread safe counter for tracking simultaneous PTT activations.

    At most PTT_MAX_COUNT PTT lines can be active at one time and this information needs to be
    shared across all accessories and amplifiers.
    '''

    PTT_MAX_COUNT = 1

    def __init__(self) -> None:
        '''Create a PTT counter initialized to 0.'''
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


class GPIOPin:
    """GPIO pin wrapper using gpiod library.

    Provides a common interface for the gpiod library.
    """

    def __init__(self, pin: int, initial: int | None) -> None:
        """Initialize a GPIO pin."""
        self.pin = pin
        self.chip_path = config['GPIO-CHIP']['path']
        self._chip = gpiod.Chip(self.chip_path)
        self._initial = initial
        self._request: gpiod.LineRequest | None = None
        self._direction: str | None = None

    def read(self) -> int:
        """Read the current value of the GPIO pin."""
        if self._direction != IN:
            self.set_direction(IN)

        if self._request is None:
            raise RuntimeError("GPIO pin request not initialized")

        return self._request.get_value(self.pin).value

    def write(self, value: int) -> None:
        """Write new value for the GPIO pin."""
        if self._direction != OUT:
            self.set_direction(OUT)

        if self._request is None:
            raise RuntimeError("GPIO pin request not initialized")

        self._request.set_value(self.pin, gpiod.line.Value(value))

    def get_direction(self) -> str | None:
        """Get the current direction of the GPIO pin."""
        return self._direction

    def set_direction(self, direction: str) -> None:
        """Set the direction of the GPIO pin."""
        if self._request:
            self._request.release()
            self._request = None

        if direction == OUT:
            config = gpiod.LineSettings(
                direction=gpiod.line.Direction.OUTPUT, output_value=gpiod.line.Value(self._initial)
            )
        elif direction == IN:
            config = gpiod.LineSettings(direction=gpiod.line.Direction.INPUT)
        else:
            raise ValueError(f"Invalid direction: {direction}")

        self._request = self._chip.request_lines(consumer="stationd", config={self.pin: config})
        self._direction = direction

    def __del__(self) -> None:
        """Cleanup GPIO resources."""
        if hasattr(self, '_request') and self._request:
            self._request.release()
        if hasattr(self, '_chip') and self._chip:
            self._chip.close()


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


def get_state(gpiopin: GPIOPin) -> str:
    """Get the current state of a given GPIO pin."""
    if gpiopin.read() == ON:
        return 'ON'
    return 'OFF'


def read_temp(path: Path) -> str:
    """Read temperature from a persistent file handle and send response."""
    with path.open('rb', buffering=0) as o:
        temp = float(o.read()) / 1000
    return f'temp: {temp!s}\n'


def get_status(gpiopin: GPIOPin, command: list[str]) -> str:
    """Get a formatted status string for a GPIO pin."""
    return f'{command[0]} {command[1]} {get_state(gpiopin)}\n'


def assert_out(gpiopin: GPIOPin) -> GPIOPin:
    """Ensure a GPIO pin is configured as an output pin."""
    if gpiopin.get_direction() != OUT:
        gpiopin.set_direction(OUT)
    return gpiopin


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
