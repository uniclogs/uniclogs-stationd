"""Station daemon module for controlling RF amplifiers and accessories.

This module provides the main server functionality for the uniclogs-stationd
system, handling UDP commands for controlling RF amplifiers, accessories,
and other hardware components.
"""

import configparser
import logging
import socket
import threading
import time
from multiprocessing import Manager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import accessory as acc
from . import amplifier as amp
from .gpio.gpio import HIGH, LOW, OUT, GPIOPin

# Module logger
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from multiprocessing.managers import DictProxy

# Config File
config = configparser.ConfigParser()
config.read('config.ini')

# Constants
ON = HIGH
OFF = LOW
LEFT = HIGH
RIGHT = LOW

PTT_COOLDOWN = 120  # In seconds
SLEEP_TIMER = 0.1
PTT_MAX_COUNT = 1

# UniClOGS UPB sensor
TEMP_PATH = Path('/sys/bus/i2c/drivers/adt7410/1-004a/hwmon/hwmon2/temp1_input')


class Command:
    """Represents a command received from a client.

    Contains the parsed command, socket connection information, and
    PTT (Push-To-Talk) state tracking.
    """

    def __init__(
        self,
        command: list[str],
        sock: socket.socket,
        addr: tuple[str, int],
        num_active_ptt: int,
    ) -> None:
        """Initialize a Command object."""
        self.command = command
        self.sock = sock
        self.addr = addr
        self.num_active_ptt = num_active_ptt


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
        # Amplifiers
        self.vhf = amp.VHF()
        self.uhf = amp.UHF()
        self.l_band = amp.LBand()
        # Accessories
        self.vu_tx_relay = acc.VUTxRelay()
        self.satnogs_host = acc.SatnogsHost()
        self.radio_host = acc.RadioHost()
        self.rotator = acc.Rotator()
        self.sdr_b200 = acc.SDRB200()
        # Temperature sensor
        self.pi_cpu = TEMP_PATH
        # Shared dict
        self.shared: DictProxy[str, Any] = Manager().dict()
        self.shared['num_active_ptt'] = 0
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
        self, command_data: list[str], sock: socket.socket, client_address: tuple[str, int]
    ) -> None:
        """Handle incoming commands and route them to appropriate devices."""
        with self.socket_lock:
            command_obj = Command(
                command=command_data,
                sock=sock,
                addr=client_address,
                num_active_ptt=self.shared['num_active_ptt'],
            )

            try:
                device = command_obj.command[0].replace('-', '_')

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
                    command_parser(getattr(self, device), command_obj)
                    self.shared['num_active_ptt'] = command_obj.num_active_ptt
                elif len(command_obj.command) == 1 and command_obj.command[0] == 'gettemp':
                    read_temp(command_obj, self.pi_cpu)
                else:
                    invalid_command_response(command_obj)
            except PTTConflictError:
                ptt_conflict_response(command_obj)
            except PTTCooldownError as e:
                ptt_cooldown_response(command_obj, e.seconds)
            except MollyGuardError:
                molly_guard_response(command_obj)
            except MaxPTTError:
                molly_guard_response(command_obj)
            except InvalidCommandError:
                invalid_command_response(command_obj)

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


def command_parser(device: 'acc.Accessory | amp.Amplifier', command_obj: Command) -> None:
    """Parse and execute commands for hardware devices."""
    if len(command_obj.command) == 3:
        # Component Status command
        if command_obj.command[2] == 'status':
            device.component_status(command_obj)
        # Component On/Off command
        else:
            try:
                fxn_name = f'{command_obj.command[1].replace("-", "_")}_{command_obj.command[2]}'
                fxn = getattr(device, fxn_name)
                fxn(command_obj)
            except AttributeError as error:
                raise InvalidCommandError(command_obj) from error
    # Device Status Commands
    elif len(command_obj.command) == 2:
        device.device_status(command_obj)
    else:
        raise InvalidCommandError(command_obj)


def calculate_diff_sec(subtrahend: float | None) -> float | None:
    """Calculate the time difference in seconds from a past datetime to now."""
    if subtrahend is None:
        return None

    now = time.time()
    return now - subtrahend


def log(command_obj: Command, message: str) -> None:
    """Log a debug message with client address information."""
    logger.debug('ADDRESS: %s, %s', command_obj.addr, message.strip())


def get_state(gpiopin: GPIOPin | None) -> str:
    """Get the current state of a given GPIO pin."""
    if gpiopin is None:
        state = 'N/A'
    elif gpiopin.read() is ON:
        state = 'ON'
    else:
        state = 'OFF'
    return state


def read_temp(command_obj: Command, path: Path) -> None:
    """Read temperature from a persistent file handle and send response."""
    with path.open('rb', buffering=0) as o:
        temp = float(o.read()) / 1000

    temp_response(command_obj, temp)


def get_status(gpiopin: GPIOPin | None, command_obj: Command) -> str:
    """Get a formatted status string for a GPIO pin."""
    return f'{command_obj.command[0]} {command_obj.command[1]} {get_state(gpiopin)}\n'


def assert_out(gpiopin: GPIOPin) -> GPIOPin:
    """Ensure a GPIO pin is configured as an output pin."""
    if gpiopin.get_direction() != OUT:
        gpiopin.set_direction(OUT)
    return gpiopin


# Response Handling ------------------------------------------------------------


def success_response(command_obj: Command) -> None:
    """Send a success response message to the client."""
    command = command_obj.command
    message = f'SUCCESS: {command[0]} {command[1]} {command[2]}\n'
    command_obj.sock.sendto(message.encode('utf-8'), command_obj.addr)
    log(command_obj, message)


def no_change_response(command_obj: Command) -> None:
    """Send a no-change warning response to the client."""
    command = command_obj.command
    message = f'WARNING: {command[0]} {command[1]} {command[2]} No Change\n'
    command_obj.sock.sendto(message.encode('utf-8'), command_obj.addr)
    log(command_obj, message)


def molly_guard_response(command_obj: Command) -> None:
    """Send a molly guard protection response to the client."""
    message = 'Re-enter the command within the next 20 seconds if you would like to proceed\n'
    command_obj.sock.sendto(message.encode('utf-8'), command_obj.addr)
    log(command_obj, message)


def ptt_conflict_response(command_obj: Command) -> None:
    """Send a PTT conflict error response to the client."""
    command = command_obj.command
    message = f'FAIL: {command[0]} {command[1]} {command[2]} PTT Conflict\n'
    command_obj.sock.sendto(message.encode('utf-8'), command_obj.addr)
    log(command_obj, message)


def max_ptt_response(command_obj: Command) -> None:
    """Send a maximum PTT exceeded error response to the client."""
    command = command_obj.command
    message = f'Fail: {command[0]} {command[1]} {command[2]} Max PTT\n'
    command_obj.sock.sendto(message.encode('utf-8'), command_obj.addr)
    log(command_obj, message)


def ptt_cooldown_response(command_obj: Command, seconds: float) -> None:
    """Send a PTT cooldown warning response to the client."""
    message = f'WARNING: Please wait {seconds} seconds and try again\n'
    command_obj.sock.sendto(message.encode('utf-8'), command_obj.addr)
    log(command_obj, message)


def invalid_command_response(command_obj: Command) -> None:
    """Send an invalid command error response to the client."""
    message = 'FAIL: Invalid Command\n'
    command_obj.sock.sendto(message.encode('utf-8'), command_obj.addr)
    log(command_obj, message)


def status_response(command_obj: Command, status: str) -> None:
    """Send a status response to the client."""
    message = status
    command_obj.sock.sendto(message.encode('utf-8'), command_obj.addr)
    message = message.replace('\n', ', ')
    log(command_obj, message)


def temp_response(command_obj: Command, temp: float) -> None:
    """Send a temperature readout response to the client."""
    message = f'temp: {temp!s}\n'
    command_obj.sock.sendto(message.encode('utf-8'), command_obj.addr)
    log(command_obj, message)


# Exceptions -------------------------------------------------------------------


class MollyGuardError(Exception):
    """Exception raised when molly guard protection is triggered.

    Used to prevent accidental execution of potentially dangerous commands by
    requiring confirmation within a time window.
    """


class PTTConflictError(Exception):
    """Exception raised when PTT operation conflicts with current state.

    The requested PTT operation cannot be performed due to conflicting hardware
    states.
    """


class MaxPTTError(Exception):
    """Exception raised when maximum PTT connections are exceeded.

    Prevents exceeding the configured maximum number of simultaneous PTT
    connections.
    """


class PTTCooldownError(Exception):
    """Exception raised when PTT cooldown period is not satisfied.

    Enforces mandatory waiting period between PTT operations for hardware
    protection.
    """

    def __init__(self, seconds: float) -> None:
        """Initialize Push-to-Talk Cooldown exception."""
        self.seconds = seconds


class InvalidCommandError(Exception):
    """Exception raised for unrecognized or malformed commands."""
