"""
Author: Steven Borrego
Date: Aug 2022
License: GPL 3.0

StationD Power management
"""
import threading
import socket
import logging
from datetime import datetime
from multiprocessing import Manager
from gpio import gpio
import configparser
import amplifier as amp
import accessory as acc

# Config
config = configparser.ConfigParser()
config.read('config.ini')

ON = gpio.HIGH
OFF = gpio.LOW
LEFT = gpio.HIGH
RIGHT = gpio.LOW

PTT_COOLDOWN = 120          # In seconds
SLEEP_TIMER = 0.1
PTT_MAX_COUNT = 1

TEMP_PATH = '/sys/class/thermal/thermal_zone0/temp'


class Command:
    def __init__(self, command, sock, addr, num_active_ptt=None):
        self.command = command
        self.sock = sock
        self.addr = addr
        self.num_active_ptt = num_active_ptt


class PersistFH:
    def __init__(self, path):
        self.path = path
        if not self.path.startswith('/sys'):
            raise RuntimeError('Using this on non-sysfs files may produce unexpected results')
        self.fh = open(self.path, 'rb', buffering=0)

    def read(self):
        self.fh.seek(0)
        return self.fh.read()[:-1]


class StationD:
    def __init__(self):
        # UDP Socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((config['NETWORK']['udp_ip'], int(config['NETWORK']['udp_port'])))
        self.socket_lock = threading.Lock()
        # Amplifiers
        self.vhf = amp.VHF()
        self.uhf = amp.UHF()
        self.l_band = amp.L_Band()
        # Accessories
        self.rx_swap = acc.RX_Swap()
        self.sbc_satnogs = acc.SBC_Satnogs()
        self.sdr_lime = acc.SDR_Lime()
        self.rotator = acc.Rotator()
        # Temperature sensor
        self.pi_cpu = PersistFH(TEMP_PATH)
        # Shared dict
        self.shared = Manager().dict()
        self.shared['num_active_ptt'] = 0
        # Logger
        logging.basicConfig(filename='activity.log',
                            format='%(asctime)s\t%(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            encoding='utf-8',
                            level=logging.DEBUG)

    def shutdown_server(self):
        print('Closing connection...')
        self.sock.close()

    def command_handler(self, command_obj):
        with self.socket_lock:
            try:
                device = command_obj.command[0].replace('-', '_')
                command_obj.num_active_ptt = self.shared['num_active_ptt']

                if device in ['vhf', 'uhf', 'l_band', 'rx_swap', 'sbc_satnogs', 'sdr_lime', 'rotator']:
                    command_parser(getattr(self, device), command_obj)
                elif len(command_obj.command) == 1 and command_obj.command[0] == 'gettemp':
                    read_temp(command_obj, self.pi_cpu)
                else:
                    raise Invalid_Command(command_obj)
            except PTT_Conflict:
                self.shared['num_active_ptt'] = command_obj.num_active_ptt
                ptt_conflict_response(command_obj)
            except PTT_Cooldown as e:
                self.shared['num_active_ptt'] = command_obj.num_active_ptt
                ptt_cooldown_response(command_obj, e.seconds)
            except Molly_Guard:
                self.shared['num_active_ptt'] = command_obj.num_active_ptt
                molly_guard_response(command_obj)
            except Max_PTT:
                self.shared['num_active_ptt'] = command_obj.num_active_ptt
                molly_guard_response(command_obj)
            except Invalid_Command:
                self.shared['num_active_ptt'] = command_obj.num_active_ptt
                invalid_command_response(command_obj)

    def command_listener(self):
        try:
            while True:
                try:
                    data, client_address = self.sock.recvfrom(1024)
                    data = data.decode().strip('\n').strip('\r').split()
                    command_obj = Command(command=data, sock=self.sock, addr=client_address)
                    c_thread = threading.Thread(target=self.command_handler, args=(command_obj,))
                    c_thread.daemon = True
                    c_thread.start()
                except OSError as err:
                    print(err)
        except KeyboardInterrupt:
            self.shutdown_server()


# Global Functions
def command_parser(device, command_obj):
    if len(command_obj.command) == 3:
        # Component Status command
        if command_obj.command[2] == 'status':
            device.component_status(command_obj)
        # Component On/Off command
        else:
            try:
                function_name = f'{command_obj.command[1].replace("-", "_")}_{command_obj.command[2]}'
                function = getattr(device, function_name)
                function(command_obj)
            except AttributeError:
                raise Invalid_Command(command_obj)
    # Device Status Commands
    elif len(command_obj.command) == 2:
        device.device_status(command_obj)
    else:
        raise Invalid_Command(command_obj)


def calculate_diff_sec(subtrahend):
    if subtrahend is None:
        return None
    now = datetime.now()
    diff = now - subtrahend
    diff_sec = diff.total_seconds()
    return diff_sec


def log(command_obj, message):
    logging.debug(f'ADDRESS: {str(command_obj.addr)}, {message.strip()}')


def get_state(gpiopin):
    if gpiopin is None:
        state = 'N/A'
    elif gpiopin.read() is ON:
        state = 'ON'
    else:
        state = 'OFF'
    return state


def read_temp(command_obj, o):
    temp = float(o.read())/1000
    temp_response(command_obj, temp)


def get_status(gpiopin, command_obj):
    status = f'{command_obj.command[0]} {command_obj.command[1]} {get_state(gpiopin)}\n'
    return status


def assert_out(gpiopin):
    if gpiopin.get_direction() != gpio.OUT:
        gpiopin.set_direction(gpio.OUT)
    return gpiopin


# Response Handling
def success_response(command_obj):
    command = command_obj.command
    message = f'SUCCESS: {command[0]} {command[1]} {command[2]}\n'
    command_obj.sock.sendto(message.encode('utf-8'), command_obj.addr)
    log(command_obj, message)


def no_change_response(command_obj):
    command = command_obj.command
    message = f'WARNING: {command[0]} {command[1]} {command[2]} No Change\n'
    command_obj.sock.sendto(message.encode('utf-8'), command_obj.addr)
    log(command_obj, message)


def molly_guard_response(command_obj):
    message = 'Re-enter the command within the next 20 seconds if you would like to proceed\n'
    command_obj.sock.sendto(message.encode('utf-8'), command_obj.addr)
    log(command_obj, message)


def ptt_conflict_response(command_obj):
    command = command_obj.command
    message = f'FAIL: {command[0]} {command[1]} {command[2]} PTT Conflict\n'
    command_obj.sock.sendto(message.encode('utf-8'), command_obj.addr)
    log(command_obj, message)


def max_ptt_response(command_obj):
    command = command_obj.command
    message = f'Fail: {command[0]} {command[1]} {command[2]} Max PTT\n'
    command_obj.sock.sendto(message.encode('utf-8'), command_obj.addr)
    log(command_obj, message)


def ptt_cooldown_response(command_obj, seconds):
    message = f'WARNING: Please wait {seconds} seconds and try again\n'
    command_obj.sock.sendto(message.encode('utf-8'), command_obj.addr)
    log(command_obj, message)


def invalid_command_response(command_obj):
    message = f'FAIL: Invalid Command\n'
    command_obj.sock.sendto(message.encode('utf-8'), command_obj.addr)
    log(command_obj, message)


def status_response(command_obj, status):
    message = status
    command_obj.sock.sendto(message.encode('utf-8'), command_obj.addr)
    message = message.replace('\n', ', ')
    log(command_obj, message)


def temp_response(command_obj, temp):
    message = f'temp: {str(temp)}\n'
    command_obj.sock.sendto(message.encode('utf-8'), command_obj.addr)
    log(command_obj, message)


# Exceptions
class Molly_Guard(Exception):
    pass


class PTT_Conflict(Exception):
    pass


class Max_PTT(Exception):
    pass


class PTT_Cooldown(Exception):
    def __init__(self, seconds):
        self.seconds = seconds


class Invalid_Command(Exception):
    pass
