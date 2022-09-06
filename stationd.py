"""
Author: Steven Borrego
Date: Aug 2022

StationD Power management
"""
import sys
import threading

from gpiozero import DigitalOutputDevice
import socket
import logging
from datetime import datetime
import time
from colorama import Fore

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
    def __init__(self, sock):
        self.name = None

        self.dow_key = None
        self.rf_ptt = None
        self.pa_power = None
        self.lna = None
        self.polarization = None

        self.ptt_off_time = None

        self.sock = sock

    def status(self, addr):
        status = []
        # Dow-key
        if self.dow_key is not None:
            status.append('ON') if self.dow_key.value == 1 else status.append('OFF')
        else:
            status.append('N/A')
        # PTT
        if self.rf_ptt is not None:
            status.append('ON') if self.rf_ptt.value == 1else status.append('OFF')
        else:
            status.append('N/A')
        # Pa-Power
        if self.pa_power is not None:
            status.append('ON') if self.pa_power.value == 1 else status.append('OFF')
        else:
            status.append('N/A')
        # LNA
        if self.lna is not None:
            status.append('ON') if self.lna.value == 1 else status.append('OFF')
        else:
            status.append('N/A')
        # Polarization
        if self.polarization is not None:
            status.append('LEFT') if self.polarization.value == 1 else status.append('RIGHT')
        else:
            status .append('N/A')

        message = 'Device: {}\n' \
                  'Dow-Key: {}\n' \
                  'Pa-Power: {}\n' \
                  'RF-PTT: {}\n' \
                  'LNA: {}\n' \
                  'Polarization: {}\n\n' \
                  .format(self.name, status[0], status[1], status[2], status[3], status[4])
        self.sock.sendto(message.encode('utf-8'), addr)
        print(Fore.BLUE + message)

    # def molly_guard(self, command, addr):
    #     device = command[0]
    #     component = command[1]
    #     state = command[2]
    #
    #     print('mollyguard() address: ' + str(addr))
    #
    #     print(Fore.YELLOW + 'Please re-enter the command if you would like to continue turning {} {} for {}'
    #           .format(component, state, device))
    #     message = 'Please re-enter the command if you would like to continue turning {} {} for {}\n'\
    #         .format(component, state, device)
    #     self.sock.sendto(message.encode('utf-8'), addr)
    #     # Get confirmation, timeout after 20 seconds
    #     try:
    #         while True:
    #             self.sock.settimeout(20)
    #             data, addr = self.sock.recvfrom(1024)
    #             guard = data.decode().strip('\n').strip('\r').split()
    #             if guard == command:
    #                 self.sock.settimeout(None)
    #                 return True
    #             else:
    #                 self.sock.settimeout(None)
    #                 return False
    #     except socket.timeout:
    #         print(Fore.RED + 'Command has timed out')
    #         message = 'Command has timed out\n'
    #         self.sock.sendto(message.encode('utf-8'), addr)
    #         self.sock.settimeout(None)
    #         return False

    def calculate_ptt_off_time(self):
        # TO-DO: Overflow guard?
        now = datetime.now()
        diff = now - self.ptt_off_time
        diff_sec = diff.total_seconds()
        return diff_sec

    def dow_key_on(self, addr):
        # Fail if PTT is on
        if self.rf_ptt.value == ON:
            print(Fore.RED + 'dow-key state cannot be changed while PTT is on')
            message = 'dow-key state cannot be changed while PTT is on\n'
            self.sock.sendto(message.encode('utf-8'), addr)
            return

        if self.dow_key.value != ON:
            self.dow_key.on()
            message = 'dow-key has been successfully turned on\n'
            self.sock.sendto(message.encode('utf-8'), addr)

    def dow_key_off(self, addr):
        # Fail if PTT is on
        if self.rf_ptt.value == ON:
            print(Fore.RED + 'dow-key state cannot be changed while PTT is on')
            message = 'dow-key state cannot be changed while PTT is on\n'
            self.sock.sendto(message.encode('utf-8'), addr)
            return

        if self.dow_key.value != OFF:
            self.dow_key.off()
            message = 'dow-key has been successfully turned off\n'
            self.sock.sendto(message.encode('utf-8'), addr)

    def rf_ptt_on(self, command, addr, ptt_flag):
        if self.pa_power.value != ON:
            print(Fore.RED + 'pa-power must be on in order to use PTT')
            message = 'pa-power must be on in order to use PTT\n'
            self.sock.sendto(message.encode('utf-8'), addr)
            return

        if self.rf_ptt.value != ON:
            #  Turn off Lna, cool down before turning on ptt
            if self.lna.value != OFF:
                self.lna.off()
                time.sleep(0.1)
            self.rf_ptt.on()
            ptt_flag = True
            success(command, self.sock, addr)
        else:
            no_change(command, self.sock, addr)

        return ptt_flag

    def rf_ptt_off(self, command, addr, ptt_flag):
        if self.rf_ptt.value != OFF:
            self.rf_ptt.off()
            ptt_flag = False
            success(command, self.sock, addr)
            #  set time ptt turned off
            self.ptt_off_time = datetime.now()
        else:
            no_change(command, self.sock, addr)

        return ptt_flag

    def pa_power_on(self, command, addr):
        if self.pa_power.value != ON:
            self.pa_power.on()
            success(command, self.sock, addr)
            self.dow_key_on(addr)
        else:
            no_change(command, self.sock, addr)

    def pa_power_off(self, command, addr):
        if self.pa_power.value != OFF:
            #  Check PTT off for at least 2 minutes
            if self.ptt_off_time is None:
                self.pa_power.off()
                success(command, self.sock, addr)
                self.dow_key_off(addr)
            elif self.rf_ptt.value == ON:
                print(Fore.RED + 'Cannot turn off pa-power while PTT is on.')
                message = 'Cannot turn off pa-power while PTT is on\n'
                self.sock.sendto(message.encode('utf-8'), addr)
            else:
                diff_sec = self.calculate_ptt_off_time()
                if diff_sec > PTT_COOLDOWN:
                    self.pa_power.off()
                    success(command, self.sock, addr)
                    self.dow_key_off(addr)
                else:
                    print(Fore.RED + 'Please wait {} seconds and try again.'.format(round(PTT_COOLDOWN - diff_sec)))
                    message = 'Please wait {} seconds and try again.\n'.format(round(PTT_COOLDOWN - diff_sec))
                    self.sock.sendto(message.encode('utf-8'), addr)
        else:
            no_change(command, self.sock, addr)

    def lna_on(self, command, addr):
        #  Fail if PTT is on
        if self.rf_ptt.value == ON:
            print(Fore.RED + 'The LNA cannot be turned on while PTT is on for this band.')
            message = 'The LNA cannot be turned on while PTT is on for this band.\n'
            self.sock.sendto(message.encode('utf-8'), addr)
            return

        if self.lna.value != ON:
            # Require inverse lna and dow-key states
            if self.dow_key.value == ON:
                self.dow_key_off(addr)

            self.lna.on()
            success(command, self.sock, addr)
        else:
            no_change(command, self.sock, addr)

    def lna_off(self, command, addr):
        if self.lna.value != OFF:
            self.lna.off()
            success(command, self.sock, addr)
            # If dow-key turned off for LNA, turn it back on
            if self.pa_power.value == ON and self.dow_key.value == OFF:
                self.dow_key_on(addr)
        else:
            no_change(command, self.sock, addr)

    def polarization_left(self, command, addr):
        if self.polarization.value != LEFT:
            #  Check ptt off for at least 100ms
            if self.rf_ptt.value != OFF:
                print(Fore.RED + 'Cannot change polarization while rf-ptt is on.')
                message = 'Cannot change polarization while rf-ptt is on.\n'
                self.sock.sendto(message.encode('utf-8'), addr)
            else:
                time.sleep(0.1)
                self.polarization.on()
                success(command, self.sock, addr)
        else:
            no_change(command, self.sock, addr)

    def polarization_right(self, command, addr):
        if self.polarization.value != RIGHT:
            #  Check ptt off for at least 100ms
            if self.rf_ptt.value != OFF:
                print(Fore.RED + 'Cannot change polarization while rf-ptt is on.')
                message = 'Cannot change polarization while rf-ptt is on.\n'
                self.sock.sendto(message.encode('utf-8'), addr)
            else:
                time.sleep(0.1)
                self.polarization.off()
                success(command, self.sock, addr)
        else:
            no_change(command, self.sock, addr)


class VHF(Amplifier):
    def __init__(self, sock):
        super().__init__(sock)
        self.name = 'VHF'

        self.dow_key = DigitalOutputDevice(VHF_DOW_KEY, initial_value=False)
        self.rf_ptt = DigitalOutputDevice(VHF_RF_PTT, initial_value=False)
        self.pa_power = DigitalOutputDevice(VHF_PA_POWER, initial_value=False)
        self.lna = DigitalOutputDevice(VHF_LNA, initial_value=False)
        self.polarization = DigitalOutputDevice(VHF_POLARIZATION, initial_value=False)

    def command_parser(self, command, addr, ptt_flag):
        match command:
            case ['vhf', 'rf-ptt', 'on']:
                ptt_flag = self.rf_ptt_on(command, addr, ptt_flag)
            case ['vhf', 'rf-ptt', 'off']:
                ptt_flag = self.rf_ptt_off(command, addr, ptt_flag)
            case ['vhf', 'pa-power', 'on']:
                self.pa_power_on(command, addr)
            case ['vhf', 'pa-power', 'off']:
                self.pa_power_off(command, addr)
            case ['vhf', 'lna', 'on']:
                self.lna_on(command, addr)
            case ['vhf', 'lna', 'off']:
                self.lna_off(command, addr)
            case ['vhf', 'polarization', 'left']:
                self.polarization_left(command, addr)
            case ['vhf', 'polarization', 'right']:
                self.polarization_right(command, addr)
            case ['vhf', 'status']:
                self.status(addr)

        return ptt_flag


class UHF(Amplifier):
    def __init__(self, sock):
        super().__init__(sock)
        self.name = 'UHF'

        # self.dow_key = DigitalOutputDevice(UHF_DOW_KEY, initial_value=False)
        # self.rf_ptt = DigitalOutputDevice(UHF_RF_PTT, initial_value=False)
        # self.pa_power = DigitalOutputDevice(UHF_PA_POWER, initial_value=False)
        # self.lna = DigitalOutputDevice(UHF_LNA, initial_value=False)
        # self.polarization = DigitalOutputDevice(UHF_POLARIZATION, initial_value=False)

    def command_parser(self, command, addr, ptt_flag):
        match command:
            case ['uhf', 'rf-ptt', 'on']:
                ptt_flag = self.rf_ptt_on(command, addr, ptt_flag)
            case ['uhf', 'rf-ptt', 'off']:
                ptt_flag = self.rf_ptt_off(command, addr, ptt_flag)
            case ['uhf', 'pa-power', 'on']:
                self.pa_power_on(command, addr)
            case ['uhf', 'pa-power', 'off']:
                self.pa_power_off(command, addr)
            case ['uhf', 'lna', 'on']:
                self.lna_on(command, addr)
            case ['uhf', 'lna', 'off']:
                self.lna_off(command, addr)
            case ['uhf', 'polarization', 'left']:
                self.polarization_left(command, addr)
            case ['uhf', 'polarization', 'right']:
                self.polarization_right(command, addr)
            case ['uhf', 'status']:
                self.status(addr)

        return ptt_flag


class L_Band(Amplifier):
    def __init__(self, sock):
        super().__init__(sock)
        self.name = 'L-Band'

        self.rf_ptt = DigitalOutputDevice(L_BAND_RF_PTT, initial_value=False)
        self.pa_power = DigitalOutputDevice(L_BAND_PA_POWER, initial_value=False)

    def command_parser(self, command, addr, ptt_flag):
        match command:
            case ['l-band', 'rf-ptt', 'on']:
                ptt_flag = self.rf_ptt_on(command, addr, ptt_flag)
            case ['l-band', 'rf-ptt', 'off']:
                ptt_flag = self.rf_ptt_off(command, addr, ptt_flag)
            case ['l-band', 'pa-power', 'on']:
                self.pa_power_on(command, addr)
            case ['l-band', 'pa-power', 'off']:
                self.pa_power_off(command, addr)

        return ptt_flag


class Accessory:
    def __init__(self, sock):
        self.name = None

        self.power = None

        self.sock = sock

    def status(self, addr):
        status = []
        # Power
        if self.power is not None:
            status.append('ON') if self.power.value == 1 else status.append('OFF')
        else:
            status.append('N/A')

        message = 'Device: {}\n' \
                  'Power: {}\n\n' \
                  .format(self.name, status[0])
        self.sock.sendto(message.encode('utf-8'), addr)
        print(Fore.BLUE + message)

    def power_on(self, command, addr):
        if self.power.value != ON:
            self.power.on()
            success(command, self.sock, addr)
        else:
            no_change(command, self.sock, addr)

    def power_off(self, command, addr):
        if self.power.value != OFF:
            self.power.off()
            success(command, self.sock, addr)
        else:
            no_change(command, self.sock, addr)


class RX_Swap(Accessory):
    def __init__(self, sock):
        super().__init__(sock)
        self.name = 'RX-Swap'

        self.power = DigitalOutputDevice(RX_SWAP_POWER, initial_value=False)

    def command_parser(self, command, addr, ptt_flag):
        # Return if PTT is on
        if ptt_flag is True:
            print(Fore.RED + 'rx-swap cannot happen while PTT is active')
            message = 'rx-swap cannot happen while PTT is active\n'
            self.sock.sendto(message.encode('utf-8'), addr)
            return

        match command:
            case ['rx-swap', 'power', 'on']:
                self.power_on(command, addr)
            case ['rx-swap', 'power', 'off']:
                self.power_off(command, addr)
            case ['rx-swap', 'status']:
                self.status(addr)


class SBC_Satnogs(Accessory):
    def __init__(self, sock):
        super().__init__(sock)
        self.name = 'SBC-Satnogs'

        self.power = DigitalOutputDevice(SBC_SATNOGS_POWER, initial_value=False)

    def command_parser(self, command, addr):
        match command:
            case ['sbc-satnogs', 'power', 'on']:
                self.power_on(command, addr)
            case ['sbc-satnogs', 'power', 'off']:
                self.power_off(command, addr)
            case ['sbc-satnogs', 'status']:
                self.status(addr)


class SDR_Lime(Accessory):
    def __init__(self, sock):
        super().__init__(sock)
        self.name = 'SDR-Lime'

        self.power = DigitalOutputDevice(SDR_LIME_POWER, initial_value=False)

    def command_parser(self, command, addr):
        match command:
            case ['sdr-lime', 'power', 'on']:
                self.power_on(command, addr)
            case ['sdr-lime', 'power', 'off']:
                self.power_off(command, addr)
            case ['sdr-lime', 'status']:
                self.status(addr)


class Rotator(Accessory):
    def __init__(self, sock):
        super().__init__(sock)
        self.name = 'Rotator'

        self.power = DigitalOutputDevice(ROTATOR_POWER, initial_value=False)

    def command_parser(self, command, addr):
        match command:
            case ['rotator', 'power', 'on']:
                self.power_on(command, addr)
            case ['rotator', 'power', 'off']:
                self.power_off(command, addr)
            case ['rotator', 'status']:
                self.status(addr)


class StationD:
    def __init__(self):
        # TO-DO: get status of devices on initialization

        # UDP Socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(LISTENING_ADDRESS)
        self.socket_lock = threading.Lock()

        # Amplifiers
        self.vhf = VHF(self.sock)
        self.uhf = UHF(self.sock)
        self.l_band = L_Band(self.sock)

        # Accessories
        self.rx_swap = RX_Swap(self.sock)
        self.sbc_satnogs = SBC_Satnogs(self.sock)
        self.sdr_lime = SDR_Lime(self.sock)
        self.rotator = Rotator(self.sock)

        # PTT on/off
        self.ptt_flag = False

        # logging.basicConfig(filename='activity.log', encoding='utf-8', level=logging.DEBUG)

    def shutdown_server(self):
        print('Closing connection...')
        self.sock.close()

    def command_handler(self, data, addr):
        with self.socket_lock:
            command = data.decode().strip('\n').strip('\r').split()
            device = command[0]

            match device:
                case 'vhf':
                    self.ptt_flag = self.vhf.command_parser(command, addr, self.ptt_flag)
                case 'uhf':
                    self.ptt_flag = self.uhf.command_parser(command, addr, self.ptt_flag)
                case 'l-band':
                    self.ptt_flag = self.l_band.command_parser(command, addr, self.ptt_flag)
                case 'rx-swap':
                    self.rx_swap.command_parser(command, addr, self.ptt_flag)
                case 'sbc-satnogs':
                    self.sbc_satnogs.command_parser(command, addr)
                case 'sdr-lime':
                    self.sdr_lime.command_parser(command, addr)
                case 'rotator':
                    self.rotator.command_parser(command, addr)
                case _:
                    # Fall through to non-device specific commands
                    match command:
                        case ['status']:
                            self.vhf.status(addr)
                            self.uhf.status(addr)
                            self.l_band.status(addr)
                            self.rx_swap.status(addr)
                            self.sbc_satnogs.status(addr)
                            self.sdr_lime.status(addr)
                            self.rotator.status(addr)
                        case _:
                            print(Fore.RED + 'Invalid command')
                            message = Fore.RED + 'Invalid command\n'
                            self.sock.sendto(message.encode('utf-8'), addr)

    def command_listener(self):
        try:
            while True:
                try:
                    data, client_address = self.sock.recvfrom(1024)
                    c_thread = threading.Thread(target=self.command_handler, args=(data, client_address))
                    c_thread.start()
                except OSError as err:
                    print(err)
        except KeyboardInterrupt:
            self.shutdown_server()


def success(command, sock, addr):
    device = command[0]
    component = command[1]
    state = command[2]

    print(Fore.GREEN + '{} has successfully been turned {} for {}'.format(component, state, device))
    message = '{} has successfully been turned {} for {}\n'.format(component, state, device)
    sock.sendto(message.encode('utf-8'), addr)


def no_change(command, sock, addr):
    device = command[0]
    component = command[1]
    state = command[2]

    print(Fore.YELLOW + '{} is already {} for {}.'.format(component, state, device))
    message = '{} is already {} for {}\n'.format(component, state, device)
    sock.sendto(message.encode('utf-8'), addr)


def main():
    sd = StationD()
    sd.command_listener()


if __name__ == "__main__":
    print('===============================')
    print('Station Daemon Power Management')
    print('===============================')

    main()
