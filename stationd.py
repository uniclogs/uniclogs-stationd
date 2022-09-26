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
import time
from multiprocessing import Manager
from gpio import gpio


# UDP
UDP_IP = '127.0.0.1'
UDP_PORT = 5005
LISTENING_ADDRESS = (UDP_IP, UDP_PORT)

# GPIO Pins
VHF_DOW_KEY = 17            # pin 11
VHF_RF_PTT = 18             # pin 12
VHF_PA_POWER = 27           # pin 13
VHF_LNA = 22                # pin 15
VHF_POLARIZATION = 23       # pin 16

# UHF_DOW_KEY = 17
# UHF_RF_PTT = 18
# UHF_PA_POWER = 27
# UHF_LNA = 22
# UHF_POLARIZATION = 23

L_BAND_RF_PTT = 24          # pin 18
L_BAND_PA_POWER = 25        # pin 22

RX_SWAP_POWER = 11          # pin 23

SBC_SATNOGS_POWER = 8       # pin 24
SDR_LIME_POWER = 2          # pin 29
ROTATOR_POWER = 6           # pin 31

ON = gpio.HIGH
OFF = gpio.LOW
LEFT = gpio.HIGH
RIGHT = gpio.LOW

PTT_COOLDOWN = 120          # In seconds
SLEEP_TIMER = 0.1
PTT_MAX_COUNT = 1


class Amplifier:
    def __init__(self):
        self.name = None

        self.dow_key = None
        self.rf_ptt = None
        self.pa_power = None
        self.lna = None
        self.polarization = None

        self.molly_guard_time = None

        # Shared data
        self.manager = Manager()
        self.shared = self.manager.dict()
        self.shared['ptt_off_time'] = datetime.now()

    def device_status(self, command_obj):
        p_state = 'LEFT' if get_state(self.polarization) is LEFT else 'RIGHT'
        status = f'{command_obj.command[0]} dow-key {get_state(self.dow_key)}\n' \
                 f'{command_obj.command[0]} rf-ptt {get_state(self.rf_ptt)}\n' \
                 f'{command_obj.command[0]} pa-power {get_state(self.pa_power)}\n' \
                 f'{command_obj.command[0]} lna {get_state(self.lna)}\n' \
                 f'{command_obj.command[0]} polarization {p_state}\n'
        raise Status(command_obj, status)

    def component_status(self, command_obj):
        component = command_obj.command[1]
        match component:
            case 'dow-key':
                status = get_status(self.dow_key, command_obj)
                raise Status(command_obj, status)
            case 'rf-ptt':
                status = get_status(self.rf_ptt, command_obj)
                raise Status(command_obj, status)
            case 'pa-power':
                status = get_status(self.pa_power, command_obj)
                raise Status(command_obj, status)
            case 'lna':
                status = get_status(self.lna, command_obj)
                raise Status(command_obj, status)
            case 'polarization':
                p_state = 'LEFT' if get_state(self.polarization) is LEFT else 'RIGHT'
                status = f'{command_obj.command[0]} {command_obj.command[1]} {p_state}\n'
                raise Status(command_obj, status)
            case _:
                raise Invalid_Command(command_obj)

    def molly_guard(self, command_obj):
        diff_sec = calculate_diff_sec(self.molly_guard_time)
        if diff_sec is None or diff_sec > 20:
            self.molly_guard_time = datetime.now()
            raise Molly_Guard(command_obj)
        else:
            # reset timer to none
            self.molly_guard_time = None
            return True

    def dow_key_on(self, command_obj):
        if self.dow_key.read() is ON:
            raise No_Change(command_obj)

        self.dow_key.write(ON)
        raise Success(command_obj)

    def dow_key_off(self, command_obj):
        if self.dow_key.read() is OFF:
            raise No_Change(command_obj)

        self.dow_key.write(OFF)
        raise Success(command_obj)

    def rf_ptt_on(self, command_obj):
        if self.rf_ptt.read() is ON:
            raise No_Change(command_obj)
        if self.pa_power.read() is OFF:
            raise PTT_Conflict(command_obj)
        if command_obj.num_active_ptt >= PTT_MAX_COUNT:
            raise Max_PTT(command_obj)

        # Enforce dow-key and ptt are same state
        if self.dow_key is not None:
            try:
                self.dow_key_on(command_obj)
            except (Success, No_Change):
                pass
        # Ptt command received, turn off LNA
        if self.lna is not None:
            try:
                self.lna_off(command_obj)
            except (Success, No_Change):
                pass
        # brief cooldown
        time.sleep(SLEEP_TIMER)
        self.rf_ptt.write(ON)
        command_obj.num_active_ptt += 1
        raise Success(command_obj)

    def rf_ptt_off(self, command_obj):
        if self.rf_ptt.read() is OFF:
            raise No_Change(command_obj)

        self.rf_ptt.write(OFF)
        #  set time ptt turned off
        self.shared['ptt_off_time'] = datetime.now()
        command_obj.num_active_ptt -= 1
        # make sure num_active_ptt never falls below 0
        if command_obj.num_active_ptt < 0:
            command_obj.num_active_ptt = 0

        # Enforce dow-key and ptt are same state
        if self.dow_key is not None:
            try:
                self.dow_key_off(command_obj)
            except (Success, No_Change):
                pass
        raise Success(command_obj)

    def pa_power_on(self, command_obj):
        if self.pa_power.read() is ON:
            raise No_Change(command_obj)
        if self.molly_guard(command_obj):
            if self.dow_key is not None:
                try:
                    self.dow_key_on(command_obj)
                except (Success, No_Change):
                    pass

            self.pa_power.write(ON)
            raise Success(command_obj)

    def pa_power_off(self, command_obj):
        if self.pa_power.read() is OFF:
            raise No_Change(command_obj)
        if self.rf_ptt.read() is ON:
            raise PTT_Conflict(command_obj)
        #  Check PTT off for at least 2 minutes
        diff_sec = calculate_diff_sec(self.shared['ptt_off_time'])
        if diff_sec > PTT_COOLDOWN:
            if self.dow_key is not None:
                try:
                    self.dow_key_off(command_obj)
                except (Success, No_Change):
                    pass
            self.pa_power.write(OFF)
            raise Success(command_obj)
        else:
            raise PTT_Cooldown(command_obj, round(PTT_COOLDOWN - diff_sec))

    def lna_on(self, command_obj):
        if self.lna.read() is ON:
            raise No_Change(command_obj)
        #  Fail if PTT is on
        if self.rf_ptt.read() is ON:
            raise PTT_Conflict(command_obj)

        self.lna.write(ON)
        raise Success(command_obj)

    def lna_off(self, command_obj):
        if self.lna.read() is OFF:
            raise No_Change(command_obj)

        self.lna.write(OFF)
        raise Success(command_obj)

    def polarization_left(self, command_obj):
        if self.polarization.read() is LEFT:
            raise No_Change(command_obj)
        if self.rf_ptt.read() is ON:
            raise PTT_Conflict(command_obj)

        # brief cooldown
        time.sleep(SLEEP_TIMER)
        self.polarization.write(LEFT)
        raise Success(command_obj)

    def polarization_right(self, command_obj):
        if self.polarization.read() is RIGHT:
            raise No_Change(command_obj)
        if self.rf_ptt.read() is ON:
            raise PTT_Conflict(command_obj)

        # brief cooldown
        time.sleep(SLEEP_TIMER)
        self.polarization.write(RIGHT)
        raise Success(command_obj)


class VHF(Amplifier):
    def __init__(self):
        super().__init__()
        self.name = 'VHF'
        # Dow-key
        self.dow_key = gpio.GPIOPin(VHF_DOW_KEY, None, initial=None)
        self.dow_key = assert_out(self.dow_key)
        # PTT
        self.rf_ptt = gpio.GPIOPin(VHF_RF_PTT, None, initial=None)
        self.rf_ptt = assert_out(self.rf_ptt)
        # TX
        self.pa_power = gpio.GPIOPin(VHF_PA_POWER, None, initial=None)
        self.pa_power = assert_out(self.pa_power)
        # RX
        self.lna = gpio.GPIOPin(VHF_LNA, None, initial=None)
        self.lna = assert_out(self.lna)
        # Polarization
        self.polarization = gpio.GPIOPin(VHF_POLARIZATION, None, initial=None)
        self.polarization = assert_out(self.polarization)


class UHF(Amplifier):
    def __init__(self):
        super().__init__()
        self.name = 'UHF'
        # # Dow-key
        # self.dow_key = gpio.GPIOPin(UHF_DOW_KEY, None, initial=None)
        # self.dow_key = assert_out(self.dow_key)
        # # PTT
        # self.rf_ptt = gpio.GPIOPin(UHF_RF_PTT, None, initial=None)
        # self.rf_ptt = assert_out(self.rf_ptt)
        # # TX
        # self.pa_power = gpio.GPIOPin(UHF_PA_POWER, None, initial=None)
        # self.pa_power = assert_out(self.pa_power)
        # # RX
        # self.lna = gpio.GPIOPin(UHF_LNA, None, initial=None)
        # self.lna = assert_out(self.lna)
        # # Polarization
        # self.polarization = gpio.GPIOPin(UHF_POLARIZATION, None, initial=None)
        # self.polarization = assert_out(self.polarization)


class L_Band(Amplifier):
    def __init__(self):
        super().__init__()
        self.name = 'L-Band'
        # PTT
        self.rf_ptt = gpio.GPIOPin(L_BAND_RF_PTT, None, initial=None)
        self.rf_ptt = assert_out(self.rf_ptt)
        # TX
        self.pa_power = gpio.GPIOPin(L_BAND_PA_POWER, None, initial=None)
        self.pa_power = assert_out(self.pa_power)


class Accessory:
    def __init__(self):
        self.name = None
        self.power = None

    def device_status(self, command_obj):
        status = f'{command_obj.command[0]} power {get_state(self.power)}\n'
        raise Status(command_obj, status)

    def component_status(self, command_obj):
        component = command_obj.command[1]
        match component:
            case 'power':
                status = get_status(self.power, command_obj)
                raise Status(command_obj, status)
            case _:
                raise Invalid_Command(command_obj)

    def rx_swap_ptt_check(self, command_obj):
        if isinstance(self, RX_Swap) and command_obj.num_active_ptt > 0:
            raise PTT_Conflict(command_obj)

    def power_on(self, command_obj):
        # RX-Swap cannot happen while any PTT is active
        self.rx_swap_ptt_check(command_obj)
        if self.power.read() is ON:
            raise No_Change(command_obj)

        self.power.write(ON)
        raise Success(command_obj)

    def power_off(self, command_obj):
        # RX-Swap cannot happen while any PTT is active
        self.rx_swap_ptt_check(command_obj)
        if self.power.read() is OFF:
            raise No_Change(command_obj)

        self.power.write(OFF)
        raise Success(command_obj)


class RX_Swap(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'RX-Swap'
        # Power
        self.power = gpio.GPIOPin(RX_SWAP_POWER, None, initial=None)
        self.power = assert_out(self.power)


class SBC_Satnogs(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'SBC-Satnogs'
        # Power
        self.power = gpio.GPIOPin(SBC_SATNOGS_POWER, None, initial=None)
        self.power = assert_out(self.power)


class SDR_Lime(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'SDR-Lime'
        # Power
        self.power = gpio.GPIOPin(SDR_LIME_POWER, None, initial=None)
        self.power = assert_out(self.power)


class Rotator(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'Rotator'
        # Power
        self.power = gpio.GPIOPin(ROTATOR_POWER, None, initial=None)
        self.power = assert_out(self.power)


class Command:
    def __init__(self, command, sock, addr, num_active_ptt=None):
        self.command = command
        self.sock = sock
        self.addr = addr
        self.num_active_ptt = num_active_ptt


class StationD:
    def __init__(self):
        # UDP Socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(LISTENING_ADDRESS)
        self.socket_lock = threading.Lock()

        # Amplifiers
        self.vhf = VHF()
        self.uhf = UHF()
        self.l_band = L_Band()

        # Accessories
        self.rx_swap = RX_Swap()
        self.sbc_satnogs = SBC_Satnogs()
        self.sdr_lime = SDR_Lime()
        self.rotator = Rotator()

        # Shared dict
        self.manager = Manager()
        self.shared = self.manager.dict()
        self.shared['num_active_ptt'] = 0

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
                else:
                    raise Invalid_Command(command_obj)
            except (Status, Success, No_Change, PTT_Conflict, PTT_Cooldown, Molly_Guard, Max_PTT, Invalid_Command) as e:
                self.shared['num_active_ptt'] = command_obj.num_active_ptt
                e.send_response()

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


def get_state(gpiopin):
    if gpiopin is None:
        state = 'N/A'
    elif gpiopin.read() is ON:
        state = 'ON'
    else:
        state = 'OFF'
    return state


def get_status(gpiopin, command_obj):
    status = f'{command_obj.command[0]} {command_obj.command[1]} {get_state(gpiopin)}\n'
    return status


def assert_out(gpiopin):
    if gpiopin.get_direction() != gpio.OUT:
        gpiopin.set_direction(gpio.OUT)
    return gpiopin


# Exceptions
class Success(Exception):
    def __init__(self, command_obj):
        self.command_obj = command_obj

    def send_response(self):
        command = self.command_obj.command
        message = f'SUCCESS: {command[0]} {command[1]} {command[2]}\n'
        self.command_obj.sock.sendto(message.encode('utf-8'), self.command_obj.addr)
        logging.debug(f'ADDRESS: {str(self.command_obj.addr)}, {message.strip()}')


class No_Change(Exception):
    def __init__(self, command_obj):
        self.command_obj = command_obj

    def send_response(self):
        command = self.command_obj.command
        message = f'WARNING: {command[0]} {command[1]} {command[2]} No Change\n'
        self.command_obj.sock.sendto(message.encode('utf-8'), self.command_obj.addr)
        logging.debug(f'ADDRESS: {str(self.command_obj.addr)}, {message.strip()}')


class Status(Exception):
    def __init__(self, command_obj, status):
        self.command_obj = command_obj
        self.status = status

    def send_response(self):
        message = self.status
        self.command_obj.sock.sendto(message.encode('utf-8'), self.command_obj.addr)
        message = message.replace('\n', ', ')
        logging.debug(f'ADDRESS: {str(self.command_obj.addr)}, {message.strip()}')


class Molly_Guard(Exception):
    def __init__(self, command_obj):
        self.command_obj = command_obj

    def send_response(self):
        message = 'Re-enter the command within the next 20 seconds if you would like to proceed\n'
        self.command_obj.sock.sendto(message.encode('utf-8'), self.command_obj.addr)
        logging.debug(f'ADDRESS: {str(self.command_obj.addr)}, {message.strip()}')


class PTT_Conflict(Exception):
    def __init__(self, command_obj):
        self.command_obj = command_obj

    def send_response(self):
        command = self.command_obj.command
        message = f'FAIL: {command[0]} {command[1]} {command[2]} PTT Conflict\n'
        self.command_obj.sock.sendto(message.encode('utf-8'), self.command_obj.addr)
        logging.debug(f'ADDRESS: {str(self.command_obj.addr)}, {message.strip()}')


class Max_PTT(Exception):
    def __init__(self, command_obj):
        self.command_obj = command_obj

    def send_response(self):
        command = self.command_obj.command
        message = f'Fail: {command[0]} {command[1]} {command[2]} Max PTT\n'
        self.command_obj.sock.sendto(message.encode('utf-8'), self.command_obj.addr)
        logging.debug(f'ADDRESS: {str(self.command_obj.addr)}, {message.strip()}')


class PTT_Cooldown(Exception):
    def __init__(self, command_obj, seconds):
        self.command_obj = command_obj
        self.seconds = seconds

    def send_response(self):
        message = f'WARNING: Please wait {self.seconds} seconds and try again\n'
        self.command_obj.sock.sendto(message.encode('utf-8'), self.command_obj.addr)
        logging.debug(f'ADDRESS: {str(self.command_obj.addr)}, {message.strip()}')


class Invalid_Command(Exception):
    def __init__(self, command_obj):
        self.command_obj = command_obj

    def send_response(self):
        message = f'FAIL: Invalid Command\n'
        self.command_obj.sock.sendto(message.encode('utf-8'), self.command_obj.addr)
        logging.debug(f'ADDRESS: {str(self.command_obj.addr)}, {message.strip()}')


if __name__ == "__main__":
    print('===============================')
    print('Station Daemon Power Management')
    print('===============================')

    sd = StationD()
    sd.command_listener()
