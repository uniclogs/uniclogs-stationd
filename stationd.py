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
        command_obj.status = f'{command_obj.command[0]} dow-key {get_state(self.dow_key)}\n' \
                             f'{command_obj.command[0]} rf-ptt {get_state(self.rf_ptt)}\n' \
                             f'{command_obj.command[0]} pa-power {get_state(self.pa_power)}\n' \
                             f'{command_obj.command[0]} lna {get_state(self.lna)}\n' \
                             f'{command_obj.command[0]} polarization {p_state}\n'
        raise Status(command_obj)

    def component_status(self, command_obj):
        component = command_obj.command[1]
        match component:
            case 'dow-key':
                command_obj.status = get_status(self.dow_key, command_obj)
                raise Status(command_obj)
            case 'rf-ptt':
                command_obj.status = get_status(self.rf_ptt, command_obj)
                raise Status(command_obj)
            case 'pa-power':
                command_obj.status = get_status(self.pa_power, command_obj)
                raise Status(command_obj)
            case 'lna':
                command_obj.status = get_status(self.lna, command_obj)
                raise Status(command_obj)
            case 'polarization':
                p_state = 'LEFT' if get_state(self.polarization) is LEFT else 'RIGHT'
                command_obj.status = f'{command_obj.command[0]} {command_obj.command[1]} {p_state}\n'
                raise Status(command_obj)

    def molly_guard(self, command_obj):
        diff_sec = calculate_diff_sec(self.molly_guard_time)
        if diff_sec is None or diff_sec > 20:
            self.molly_guard_time = datetime.now()
            command_obj.molly_guard_response()
            return False
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

    def command_parser(self, command_obj):
        match command_obj.command:
            case ['vhf', 'dow-key', 'status']:
                self.component_status(command_obj)
            case ['vhf', 'rf-ptt', 'on']:
                self.rf_ptt_on(command_obj)
            case ['vhf', 'rf-ptt', 'off']:
                self.rf_ptt_off(command_obj)
            case ['vhf', 'rf-ptt', 'status']:
                self.component_status(command_obj)
            case ['vhf', 'pa-power', 'on']:
                if self.molly_guard(command_obj):
                    self.pa_power_on(command_obj)
            case ['vhf', 'pa-power', 'off']:
                self.pa_power_off(command_obj)
            case['vhf', 'pa-power', 'status']:
                self.component_status(command_obj)
            case ['vhf', 'lna', 'on']:
                self.lna_on(command_obj)
            case ['vhf', 'lna', 'off']:
                self.lna_off(command_obj)
            case ['vhf', 'lna', 'status']:
                self.component_status(command_obj)
            case ['vhf', 'polarization', 'left']:
                self.polarization_left(command_obj)
            case ['vhf', 'polarization', 'right']:
                self.polarization_right(command_obj)
            case ['vhf', 'polarization', 'status']:
                self.component_status(command_obj)
            case ['vhf', 'status']:
                self.device_status(command_obj)
            case _:
                raise Invalid_Command(command_obj)


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

    def command_parser(self, command_obj):
        match command_obj.command:
            case['uhf', 'dow-key', 'status']:
                self.component_status(command_obj)
            case ['uhf', 'rf-ptt', 'on']:
                self.rf_ptt_on(command_obj)
            case ['uhf', 'rf-ptt', 'off']:
                self.rf_ptt_off(command_obj)
            case ['uhf', 'rf-ptt', 'status']:
                self.component_status(command_obj)
            case ['uhf', 'pa-power', 'on']:
                if self.molly_guard(command_obj):
                    self.pa_power_on(command_obj)
            case ['uhf', 'pa-power', 'off']:
                self.pa_power_off(command_obj)
            case ['uhf', 'pa-power', 'status']:
                self.component_status(command_obj)
            case ['uhf', 'lna', 'on']:
                self.lna_on(command_obj)
            case ['uhf', 'lna', 'off']:
                self.lna_off(command_obj)
            case ['uhf', 'lna', 'status']:
                self.component_status(command_obj)
            case ['uhf', 'polarization', 'left']:
                self.polarization_left(command_obj)
            case ['uhf', 'polarization', 'right']:
                self.polarization_right(command_obj)
            case ['uhf', 'polarization', 'status']:
                self.component_status(command_obj)
            case ['uhf', 'status']:
                self.device_status(command_obj)
            case _:
                raise Invalid_Command(command_obj)


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

    def command_parser(self, command_obj):
        match command_obj.command:
            case ['l-band', 'rf-ptt', 'on']:
                self.rf_ptt_on(command_obj)
            case ['l-band', 'rf-ptt', 'off']:
                self.rf_ptt_off(command_obj)
            case ['l-band', 'rf-ptt', 'status']:
                self.component_status(command_obj)
            case ['l-band', 'pa-power', 'on']:
                if self.molly_guard(command_obj):
                    self.pa_power_on(command_obj)
            case ['l-band', 'pa-power', 'off']:
                self.pa_power_off(command_obj)
            case ['l-band', 'pa-power', 'status']:
                self.component_status(command_obj)
            case ['l-band', 'status']:
                self.device_status(command_obj)
            case _:
                raise Invalid_Command(command_obj)


class Accessory:
    def __init__(self):
        self.name = None
        self.power = None

    def device_status(self, command_obj):
        command_obj.status = f'{command_obj.command[0]} power {get_state(self.power)}\n'
        raise Status(command_obj)

    def component_status(self, command_obj):
        component = command_obj.command[1]
        match component:
            case 'power':
                command_obj.status = get_status(self.power, command_obj)
                raise Status(command_obj)

    def power_on(self, command_obj):
        if self.power.read() is ON:
            raise No_Change(command_obj)

        self.power.write(ON)
        raise Success(command_obj)

    def power_off(self, command_obj):
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

    def rx_swap_power_on(self, command_obj):
        if self.power.read() is ON:
            raise No_Change(command_obj)
        # Fail if PTT is on
        if command_obj.num_active_ptt > 0:
            raise PTT_Conflict(command_obj)

        self.power.write(ON)
        raise Success(command_obj)

    def rx_swap_power_off(self, command_obj):
        if self.power.read() is OFF:
            raise No_Change(command_obj)
        # Fail if PTT is on
        if command_obj.num_active_ptt > 0:
            raise PTT_Conflict

        self.power.write(OFF)
        raise Success(command_obj)

    def command_parser(self, command_obj):
        match command_obj.command:
            case ['rx-swap', 'power', 'on']:
                self.rx_swap_power_on(command_obj)
            case ['rx-swap', 'power', 'off']:
                self.rx_swap_power_off(command_obj)
            case ['rx-swap', 'power', 'status']:
                self.component_status(command_obj)
            case ['rx-swap', 'status']:
                self.device_status(command_obj)
            case _:
                raise Invalid_Command(command_obj)


class SBC_Satnogs(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'SBC-Satnogs'
        # Power
        self.power = gpio.GPIOPin(SBC_SATNOGS_POWER, None, initial=None)
        self.power = assert_out(self.power)

    def command_parser(self, command_obj):
        match command_obj.command:
            case ['sbc-satnogs', 'power', 'on']:
                self.power_on(command_obj)
            case ['sbc-satnogs', 'power', 'off']:
                self.power_off(command_obj)
            case ['sbc-satnogs', 'power', 'status']:
                self.component_status(command_obj)
            case ['sbc-satnogs', 'status']:
                self.device_status(command_obj)
            case _:
                raise Invalid_Command(command_obj)


class SDR_Lime(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'SDR-Lime'
        # Power
        self.power = gpio.GPIOPin(SDR_LIME_POWER, None, initial=None)
        self.power = assert_out(self.power)

    def command_parser(self, command_obj):
        match command_obj.command:
            case ['sdr-lime', 'power', 'on']:
                self.power_on(command_obj)
            case ['sdr-lime', 'power', 'off']:
                self.power_off(command_obj)
            case ['sdr-lime', 'power', 'status']:
                self.component_status(command_obj)
            case ['sdr-lime', 'status']:
                self.device_status(command_obj)
            case _:
                raise Invalid_Command(command_obj)


class Rotator(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'Rotator'
        # Power
        self.power = gpio.GPIOPin(ROTATOR_POWER, None, initial=None)
        self.power = assert_out(self.power)

    def command_parser(self, command_obj):
        match command_obj.command:
            case ['rotator', 'power', 'on']:
                self.power_on(command_obj)
            case ['rotator', 'power', 'off']:
                self.power_off(command_obj)
            case ['rotator', 'power', 'status']:
                self.component_status(command_obj)
            case ['rotator', 'status']:
                self.device_status(command_obj)
            case _:
                raise Invalid_Command(command_obj)


class Command:
    def __init__(self, command, sock, addr, status=None, num_active_ptt=None):
        self.command = command
        self.sock = sock
        self.addr = addr
        self.status = status
        self.num_active_ptt = num_active_ptt

    def success_response(self):
        message = f'SUCCESS: {self.command[0]} {self.command[1]} {self.command[2]}\n'
        self.sock.sendto(message.encode('utf-8'), self.addr)
        logging.debug(f'ADDRESS: {str(self.addr)}, {message.strip()}')

    def no_change_response(self):
        message = f'WARNING: {self.command[0]} {self.command[1]} {self.command[2]} No Change\n'
        self.sock.sendto(message.encode('utf-8'), self.addr)
        logging.debug(f'{str(datetime.now())} {message.strip()}, ADDRESS: {str(self.addr)}')

    def ptt_conflict_response(self):
        message = f'FAIL: {self.command[0]} {self.command[1]} {self.command[2]} PTT Conflict\n'
        self.sock.sendto(message.encode('utf-8'), self.addr)
        logging.debug(f'ADDRESS: {str(self.addr)}, {message.strip()}')

    def invalid_command_response(self):
        message = f'FAIL: {self.command[0]} {self.command[1]} {self.command[2]} Invalid Command\n'
        self.sock.sendto(message.encode('utf-8'), self.addr)
        logging.debug(f'ADDRESS: {str(self.addr)}, {message.strip()}')

    def status_response(self):
        message = self.status
        self.sock.sendto(message.encode('utf-8'), self.addr)
        message = message.replace('\n', ', ')
        logging.debug(f'ADDRESS: {str(self.addr)}, {message.strip()}')

    def molly_guard_response(self):
        message = 'Re-enter the command within the next 20 seconds if you would like to proceed\n'
        self.sock.sendto(message.encode('utf-8'), self.addr)
        logging.debug(f'ADDRESS: {str(self.addr)}, {message.strip()}')

    def max_ptt_response(self):
        message = f'Fail: {self.command[0]} {self.command[1]} {self.command[2]} Max PTT\n'
        self.sock.sendto(message.encode('utf-8'), self.addr)
        logging.debug(f'ADDRESS: {str(self.addr)}, {message.strip()}')

    def ptt_cooldown_response(self, seconds):
        message = f'WARNING: Please wait {seconds} seconds and try again\n'
        self.sock.sendto(message.encode('utf-8'), self.addr)
        logging.debug(f'ADDRESS: {str(self.addr)}, {message.strip()}')


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
                device = command_obj.command[0]
                command_obj.num_active_ptt = self.shared['num_active_ptt']

                match device:
                    case 'vhf':
                        self.vhf.command_parser(command_obj)
                    case 'uhf':
                        self.uhf.command_parser(command_obj)
                    case 'l-band':
                        self.l_band.command_parser(command_obj)
                    case 'rx-swap':
                        self.rx_swap.command_parser(command_obj)
                    case 'sbc-satnogs':
                        self.sbc_satnogs.command_parser(command_obj)
                    case 'sdr-lime':
                        self.sdr_lime.command_parser(command_obj)
                    case 'rotator':
                        self.rotator.command_parser(command_obj)
                    case _:
                        raise Invalid_Command(command_obj)
            except (Status, Success, No_Change, PTT_Conflict, PTT_Cooldown, Max_PTT, Invalid_Command) as e:
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
                    c_thread.start()
                except OSError as err:
                    print(err)
        except KeyboardInterrupt:
            self.shutdown_server()


# Global Functions
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
        self.command_obj.success_response()


class No_Change(Exception):
    def __init__(self, command_obj):
        self.command_obj = command_obj

    def send_response(self):
        self.command_obj.no_change_response()


class Status(Exception):
    def __init__(self, command_obj):
        self.command_obj = command_obj

    def send_response(self):
        self.command_obj.status_response()


class PTT_Conflict(Exception):
    def __init__(self, command_obj):
        self.command_obj = command_obj

    def send_response(self):
        self.command_obj.ptt_conflict_response()


class Max_PTT(Exception):
    def __init__(self, command_obj):
        self.command_obj = command_obj

    def send_response(self):
        self.command_obj.max_ptt_response()


class PTT_Cooldown(Exception):
    def __init__(self, command_obj, seconds):
        self.command_obj = command_obj
        self.seconds = seconds

    def send_response(self):
        self.command_obj.ptt_cooldown_response(self.seconds)


class Invalid_Command(Exception):
    def __init__(self, command_obj):
        self.command_obj = command_obj

    def send_response(self):
        self.command_obj.invalid_command_response()


if __name__ == "__main__":
    print('===============================')
    print('Station Daemon Power Management')
    print('===============================')

    sd = StationD()
    sd.command_listener()
