"""
Author: Steven Borrego
Date: Aug 2022

StationD Power management
"""
import threading
from gpiozero import DigitalOutputDevice
import socket
import logging
from datetime import datetime
import time
from multiprocessing import Manager
from colorama import Fore
from colorama import init as colorama_init
import gpio

colorama_init(autoreset=True)

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

ON = 1
OFF = 0
PTT_COOLDOWN = 120          # In seconds

LEFT = 1
RIGHT = 0


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
        self.shared['ptt_off_time'] = None

    def status(self, command_obj):
        status = {}
        # Dow-key
        if self.dow_key is not None:
            status.update({'dow-key': 'ON'}) if self.dow_key.value == 1 else status.update({'dow-key': 'OFF'})
        else:
            status.update({'dow-key': 'N/A'})
        # Pa-Power
        if self.pa_power is not None:
            status.update({'pa-power': 'ON'}) if self.pa_power.value == 1 else status.update({'pa-power': 'OFF'})
        else:
            status.update({'pa-power': 'N/A'})
        # PTT
        if self.rf_ptt is not None:
            status.update({'rf-ptt': 'ON'}) if self.rf_ptt.value == 1 else status.update({'rf-ptt': 'OFF'})
        else:
            status.update({'rf-ptt': 'N/A'})
        # LNA
        if self.lna is not None:
            status.update({'lna': 'ON'}) if self.lna.value == 1 else status.update({'lna':'OFF'})
        else:
            status.update({'lna': 'OFF'})
        # Polarization
        if self.polarization is not None:
            status.update({'polarization': 'LEFT'}) if self.polarization.value == 1 \
        else status.update({'polarization': 'RIGHT'})
        else:
            status .update({'polarization': 'N/A'})

        message = 'Device: {}\n' \
                  'Dow-Key: {}\n' \
                  'Pa-Power: {}\n' \
                  'RF-PTT: {}\n' \
                  'LNA: {}\n' \
                  'Polarization: {}\n\n' \
                  .format(self.name, status['dow-key'], status['pa-power'],
                          status['rf-ptt'], status['lna'], status['polarization'])
        command_obj.send_response(message)

    def molly_guard(self, command_obj):
        try:
            # first command request
            if self.molly_guard_time is None:
                # set timer
                self.molly_guard_time = datetime.now()
                message = Fore.YELLOW + 'Re-enter the command within the next 20 seconds' \
                                        ' if you would like to proceed \n'
                command_obj.send_response(message)
                return False

            # second command request
            now = datetime.now()
            diff = now - self.molly_guard_time
            diff_sec = diff.total_seconds()
            if diff_sec > 20:
                # took too long
                raise Time_Out
            else:
                # reset timer to none
                self.molly_guard_time = None
                return True
        except Time_Out:
            message = Fore.RED + 'The command has timed out\n'
            command_obj.send_response(message)
            self.molly_guard_time = None
            return False
        except Exception as error:
            print(error)

    def calculate_ptt_off_time(self):
        # TO-DO: Overflow guard?
        now = datetime.now()
        diff = now - self.shared['ptt_off_time']
        diff_sec = diff.total_seconds()
        return diff_sec

    def dow_key_on(self, command_obj):
        try:
            if self.dow_key.value == ON:
                raise Redundant_Request
            # Fail if PTT is on
            if self.rf_ptt.value == ON:
                raise PTT_Conflict

            self.dow_key.on()
            message = Fore.GREEN + 'dow-key has been successfully turned on\n'
            command_obj.send_response(message)
        except Redundant_Request:
            command_obj.no_change_response()
        except PTT_Conflict:
            message = Fore.RED + 'dow-key state cannot be changed while PTT is on\n'
            command_obj.send_response(message)
        except Exception as error:
            print(error)

    def dow_key_off(self, command_obj):
        try:
            if self.dow_key.value == OFF:
                raise Redundant_Request
            # Fail if PTT is on
            if self.rf_ptt.value == ON:
                raise PTT_Conflict

            self.dow_key.off()
            message = Fore.GREEN + 'dow-key has been successfully turned off\n'
            command_obj.send_response(message)
        except Redundant_Request:
            command_obj.no_change_response()
        except PTT_Conflict:
            message = Fore.RED + 'dow-key state cannot be changed while PTT is on\n'
            command_obj.send_response(message)
        except Exception as error:
            print(error)

    def rf_ptt_on(self, command_obj, ptt_flag):
        try:
            if self.rf_ptt.value == ON:
                raise Redundant_Request
            if self.pa_power.value == OFF:
                raise TX_Off

            #  Turn off Lna, cool down before turning on ptt
            if self.lna.value == ON:
                self.lna.off()
                time.sleep(0.1)

            self.rf_ptt.on()
            ptt_flag = True
            command_obj.success_response()
        except Redundant_Request:
            command_obj.no_change_response()
        except TX_Off:
            message = Fore.RED + 'pa-power must be on in order to use PTT\n'
            command_obj.send_response(message)
        except Exception as error:
            print(error)

        return ptt_flag

    def rf_ptt_off(self, command_obj, ptt_flag):
        try:
            if self.rf_ptt.value == OFF:
                raise Redundant_Request

            self.rf_ptt.off()
            #  set time ptt turned off
            self.shared['ptt_off_time'] = datetime.now()
            ptt_flag = False
            command_obj.success_response()
        except Redundant_Request:
            command_obj.no_change_response()
        except Exception as error:
            print(error)

        return ptt_flag

    def pa_power_on(self, command_obj):
        try:
            if self.pa_power.value == ON:
                raise Redundant_Request

            self.pa_power.on()
            command_obj.success_response()
            self.dow_key_on(command_obj)
        except Redundant_Request:
            command_obj.no_change_response()
        except Exception as error:
            print(error)

    def pa_power_off(self, command_obj):
        try:
            if self.pa_power.value == OFF:
                raise Redundant_Request
            if self.rf_ptt.value == ON:
                raise PTT_Conflict

            #  Check PTT off for at least 2 minutes
            if self.shared['ptt_off_time'] is None:
                self.pa_power.off()
                command_obj.success_response()
                self.dow_key_off(command_obj)
            else:
                diff_sec = self.calculate_ptt_off_time()
                if diff_sec > PTT_COOLDOWN:
                    self.pa_power.off()
                    command_obj.success_response()
                    self.dow_key_off(command_obj)
                else:
                    message = Fore.YELLOW + 'Please wait {} seconds and try again.\n' \
                              .format(round(PTT_COOLDOWN - diff_sec))
                    command_obj.send_response(message)
        except Redundant_Request:
            command_obj.no_change_response()
        except PTT_Conflict:
            message = Fore.RED + 'Cannot turn off pa-power while PTT is on\n'
            command_obj.send_response(message)
        except Exception as error:
            print(error)

    def lna_on(self, command_obj):
        try:
            if self.lna.value == ON:
                raise Redundant_Request
            #  Fail if PTT is on
            if self.rf_ptt.value == ON:
                raise PTT_Conflict

            # Require inverse lna and dow-key states
            if self.dow_key.value == ON:
                self.dow_key_off(command_obj)

            self.lna.on()
            command_obj.success_response()
        except Redundant_Request:
            command_obj.no_change_response()
        except PTT_Conflict:
            message = Fore.RED + 'The LNA cannot be turned on while PTT is on for this band.\n'
            command_obj.send_response(message)
        except Exception as error:
            print(error)

    def lna_off(self, command_obj):
        try:
            if self.lna.value == OFF:
                raise Redundant_Request

            self.lna.off()
            command_obj.success_response()

            # If dow-key turned off for LNA, turn it back on
            if self.pa_power.value == ON and self.dow_key.value == OFF:
                self.dow_key_on(command_obj)
        except Redundant_Request:
            command_obj.no_change_response()
        except Exception as error:
            print(error)

    def polarization_left(self, command_obj):
        try:
            if self.polarization.value == LEFT:
                raise Redundant_Request
            if self.rf_ptt.value == ON:
                raise PTT_Conflict

            time.sleep(0.1)
            self.polarization.on()
            command_obj.success_response()
        except Redundant_Request:
            command_obj.no_change_response()
        except PTT_Conflict:
            message = Fore.RED + 'Cannot change polarization while rf-ptt is on.\n'
            command_obj.send_response(message)
        except Exception as error:
            print(error)

    def polarization_right(self, command_obj):
        try:
            if self.polarization.value == RIGHT:
                raise Redundant_Request
            if self.rf_ptt.value == ON:
                raise PTT_Conflict

            time.sleep(0.1)
            self.polarization.off()
            command_obj.success_response()
        except Redundant_Request:
            command_obj.no_change_response()
        except PTT_Conflict:
            message = Fore.RED + 'Cannot change polarization while rf-ptt is on.\n'
            command_obj.send_response(message)
        except Exception as error:
            print(error)


class VHF(Amplifier):
    def __init__(self):
        super().__init__()
        self.name = 'VHF'

        self.dow_key = DigitalOutputDevice(VHF_DOW_KEY, initial_value=False)
        self.rf_ptt = DigitalOutputDevice(VHF_RF_PTT, initial_value=False)
        self.pa_power = DigitalOutputDevice(VHF_PA_POWER, initial_value=False)
        self.lna = DigitalOutputDevice(VHF_LNA, initial_value=False)
        self.polarization = DigitalOutputDevice(VHF_POLARIZATION, initial_value=False)

        # # gpio library
        # self.dow_key = gpio.GPIOPin(VHF_DOW_KEY, gpio.OUT, initial=gpio.LOW)
        # self.rf_ptt = gpio.GPIOPin(VHF_RF_PTT, gpio.OUT, initial=gpio.LOW)
        # self.pa_power = gpio.GPIOPin(VHF_PA_POWER, gpio.OUT, initial=gpio.LOW)
        # self.lna = gpio.GPIOPin(VHF_LNA, gpio.OUT, initial=gpio.LOW)
        # self.polarization = gpio.GPIOPin(VHF_POLARIZATION, gpio.OUT, initial=gpio.LOW)

    def command_parser(self, command_obj, ptt_flag):
        match command_obj.command:
            case ['vhf', 'rf-ptt', 'on']:
                ptt_flag = self.rf_ptt_on(command_obj, ptt_flag)
            case ['vhf', 'rf-ptt', 'off']:
                ptt_flag = self.rf_ptt_off(command_obj, ptt_flag)
            case ['vhf', 'pa-power', 'on']:
                if self.molly_guard(command_obj):
                    self.pa_power_on(command_obj)
            case ['vhf', 'pa-power', 'off']:
                self.pa_power_off(command_obj)
            case ['vhf', 'lna', 'on']:
                self.lna_on(command_obj)
            case ['vhf', 'lna', 'off']:
                self.lna_off(command_obj)
            case ['vhf', 'polarization', 'left']:
                self.polarization_left(command_obj)
            case ['vhf', 'polarization', 'right']:
                self.polarization_right(command_obj)
            case ['vhf', 'status']:
                self.status(command_obj)
            case _:
                command_obj.invalid_command_response()

        return ptt_flag


class UHF(Amplifier):
    def __init__(self):
        super().__init__()
        self.name = 'UHF'

        # self.dow_key = DigitalOutputDevice(UHF_DOW_KEY, initial_value=False)
        # self.rf_ptt = DigitalOutputDevice(UHF_RF_PTT, initial_value=False)
        # self.pa_power = DigitalOutputDevice(UHF_PA_POWER, initial_value=False)
        # self.lna = DigitalOutputDevice(UHF_LNA, initial_value=False)
        # self.polarization = DigitalOutputDevice(UHF_POLARIZATION, initial_value=False)

    def command_parser(self, command_obj, ptt_flag):
        match command_obj.command:
            case ['uhf', 'rf-ptt', 'on']:
                ptt_flag = self.rf_ptt_on(command_obj, ptt_flag)
            case ['uhf', 'rf-ptt', 'off']:
                ptt_flag = self.rf_ptt_off(command_obj, ptt_flag)
            case ['uhf', 'pa-power', 'on']:
                if self.molly_guard(command_obj):
                    self.pa_power_on(command_obj)
            case ['uhf', 'pa-power', 'off']:
                self.pa_power_off(command_obj)
            case ['uhf', 'lna', 'on']:
                self.lna_on(command_obj)
            case ['uhf', 'lna', 'off']:
                self.lna_off(command_obj)
            case ['uhf', 'polarization', 'left']:
                self.polarization_left(command_obj)
            case ['uhf', 'polarization', 'right']:
                self.polarization_right(command_obj)
            case ['uhf', 'status']:
                self.status(command_obj)
            case _:
                command_obj.invalid_command_response()

        return ptt_flag


class L_Band(Amplifier):
    def __init__(self):
        super().__init__()
        self.name = 'L-Band'

        self.rf_ptt = DigitalOutputDevice(L_BAND_RF_PTT, initial_value=False)
        self.pa_power = DigitalOutputDevice(L_BAND_PA_POWER, initial_value=False)

    def command_parser(self, command_obj, ptt_flag):
        match command_obj.command:
            case ['l-band', 'rf-ptt', 'on']:
                ptt_flag = self.rf_ptt_on(command_obj, ptt_flag)
            case ['l-band', 'rf-ptt', 'off']:
                ptt_flag = self.rf_ptt_off(command_obj, ptt_flag)
            case ['l-band', 'pa-power', 'on']:
                if self.molly_guard(command_obj):
                    self.pa_power_on(command_obj)
            case ['l-band', 'pa-power', 'off']:
                self.pa_power_off(command_obj)
            case _:
                command_obj.invalid_command_response()

        return ptt_flag


class Accessory:
    def __init__(self):
        self.name = None

        self.power = None

    def status(self, command_obj):
        status = {}
        # Power
        if self.power is not None:
            status.update({'power': 'ON'}) if self.power.value == 1 else status.update({'power':'OFF'})
        else:
            status.update({'power': 'N/A'})

        message = 'Device: {}\n' \
                  'Power: {}\n\n' \
                  .format(self.name, status['power'])
        command_obj.send_response(message)

    def power_on(self, command_obj):
        try:
            if self.power.value == ON:
                raise Redundant_Request

            self.power.on()
            command_obj.success_response()
        except Redundant_Request:
            command_obj.no_change_response()
        except Exception as error:
            print(error)

    def power_off(self, command_obj):
        try:
            if self.power.value == OFF:
                raise Redundant_Request

            self.power.off()
            command_obj.success_response()
        except Redundant_Request:
            command_obj.no_change_response()
        except Exception as error:
            print(error)


class RX_Swap(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'RX-Swap'

        self.power = DigitalOutputDevice(RX_SWAP_POWER, initial_value=False)

    def command_parser(self, command_obj, ptt_flag):
        # Return if PTT is on
        if ptt_flag is True:
            message = Fore.RED + 'rx-swap cannot happen while PTT is active\n'
            command_obj.send_response(message)
            return

        match command_obj.command:
            case ['rx-swap', 'power', 'on']:
                self.power_on(command_obj)
            case ['rx-swap', 'power', 'off']:
                self.power_off(command_obj)
            case ['rx-swap', 'status']:
                self.status(command_obj)
            case _:
                command_obj.invalid_command_response()


class SBC_Satnogs(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'SBC-Satnogs'

        self.power = DigitalOutputDevice(SBC_SATNOGS_POWER, initial_value=False)

    def command_parser(self, command_obj):
        match command_obj.command:
            case ['sbc-satnogs', 'power', 'on']:
                self.power_on(command_obj)
            case ['sbc-satnogs', 'power', 'off']:
                self.power_off(command_obj)
            case ['sbc-satnogs', 'status']:
                self.status(command_obj)
            case _:
                command_obj.invalid_command_response()


class SDR_Lime(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'SDR-Lime'

        self.power = DigitalOutputDevice(SDR_LIME_POWER, initial_value=False)

    def command_parser(self, command_obj):
        match command_obj.command:
            case ['sdr-lime', 'power', 'on']:
                self.power_on(command_obj)
            case ['sdr-lime', 'power', 'off']:
                self.power_off(command_obj)
            case ['sdr-lime', 'status']:
                self.status(command_obj)
            case _:
                command_obj.invalid_command_response()


class Rotator(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'Rotator'

        self.power = DigitalOutputDevice(ROTATOR_POWER, initial_value=False)

    def command_parser(self, command_obj):
        match command_obj.command:
            case ['rotator', 'power', 'on']:
                self.power_on(command_obj)
            case ['rotator', 'power', 'off']:
                self.power_off(command_obj)
            case ['rotator', 'status']:
                self.status(command_obj)
            case _:
                command_obj.invalid_command_response()


class Command:
    def __init__(self, command, sock, addr):
        self.command = command
        self.sock = sock
        self.addr = addr

    def success_response(self):
        device = self.command[0]
        component = self.command[1]
        state = self.command[2]

        message = Fore.GREEN + '{} has successfully been turned {} for {}\n'.format(component, state, device)
        logging.debug(message + str(datetime.now()))
        self.sock.sendto(message.encode('utf-8'), self.addr)

    def no_change_response(self):
        device = self.command[0]
        component = self.command[1]
        state = self.command[2]

        message = Fore.YELLOW + '{} is already {} for {}\n'.format(component, state, device)
        self.sock.sendto(message.encode('utf-8'), self.addr)

    def invalid_command_response(self):
        message = Fore.RED + 'Invalid command\n'
        self.sock.sendto(message.encode('utf-8'), self.addr)

    def send_response(self, message):
        self.sock.sendto(message.encode('utf-8'), self.addr)


class StationD:
    def __init__(self):
        # TO-DO: get status of devices on initialization

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

        # PTT on/off
        self.ptt_flag = False

        logging.basicConfig(filename='activity.log', encoding='utf-8', level=logging.DEBUG)

    def configure(self):
        pass

    def shutdown_server(self):
        print('Closing connection...')
        self.sock.close()

    def command_handler(self, command_obj):
        with self.socket_lock:
            device = command_obj.command[0]

            match device:
                case 'vhf':
                    self.ptt_flag = self.vhf.command_parser(command_obj, self.ptt_flag)
                case 'uhf':
                    self.ptt_flag = self.uhf.command_parser(command_obj, self.ptt_flag)
                case 'l-band':
                    self.ptt_flag = self.l_band.command_parser(command_obj, self.ptt_flag)
                case 'rx-swap':
                    self.rx_swap.command_parser(command_obj, self.ptt_flag)
                case 'sbc-satnogs':
                    self.sbc_satnogs.command_parser(command_obj)
                case 'sdr-lime':
                    self.sdr_lime.command_parser(command_obj)
                case 'rotator':
                    self.rotator.command_parser(command_obj)
                case _:
                    # Fall through to non-device specific commands
                    match command_obj.command:
                        case ['status']:
                            self.vhf.status(command_obj)
                            self.uhf.status(command_obj)
                            self.l_band.status(command_obj)
                            self.rx_swap.status(command_obj)
                            self.sbc_satnogs.status(command_obj)
                            self.sdr_lime.status(command_obj)
                            self.rotator.status(command_obj)
                        case _:
                            command_obj.invalid_command_response()

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


# Exceptions
class PTT_Conflict(Exception):
    pass


class TX_Off(Exception):
    pass


class Redundant_Request(Exception):
    pass


class Time_Out(Exception):
    pass


def main():
    sd = StationD()
    sd.command_listener()


if __name__ == "__main__":
    print('===============================')
    print('Station Daemon Power Management')
    print('===============================')

    main()
