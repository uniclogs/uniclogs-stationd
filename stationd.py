"""
Author: Steven Borrego
Date: Aug 2022

Station D Power management
"""

from gpiozero import DigitalOutputDevice
import socket
import logging
from datetime import datetime
import time
from colorama import Fore

UDP_IP = '127.0.0.1'
UDP_PORT = 5005

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
        self.dow_key = None
        self.rf_ptt = None
        self.pa_power = None
        self.lna = None
        self.polarization = None

        self.ptt_off_time = None

    @staticmethod
    def molly_guard(command):
        answer = input(Fore.YELLOW + 'Are you sure you want to turn {} {} for {}? y/n: '
                       + Fore.RESET.format(command[1], command[2], command[0]))
        if answer.lower() == 'y':
            return True
        else:
            return False

    def calculate_ptt_off_time(self):
        # TO-DO: Overflow guard?
        now = datetime.now()
        diff = now - self.ptt_off_time
        diff_sec = diff.total_seconds()

        return diff_sec

    def dow_key_on(self, command):
        if self.rf_ptt.value == ON:
            print(Fore.RED + 'dow-key state cannot be changed while PTT is on')
            return

        if self.dow_key.value != ON:
            self.dow_key.on()
            print(Fore.GREEN + 'dow-key has been turned on for {}'.format(command[0]))

    def dow_key_off(self, command):
        if self.rf_ptt.value == ON:
            print(Fore.RED + 'dow-key state cannot be changed while PTT is on')
            return

        if self.dow_key.value != OFF:
            self.dow_key.off()
            print(Fore.GREEN + 'dow-key has been turned off for {}'.format(command[0]))

    def rf_ptt_on(self, command, ptt_flag):
        if self.pa_power.value != ON:
            print(Fore.RED + 'pa-power must be on in order to use PTT')
            return

        if self.rf_ptt.value != ON:
            #  Turn off Lna, cool down before turning on ptt
            if self.lna.value != OFF:
                self.lna.off()
                time.sleep(0.1)
            self.rf_ptt.on()
            ptt_flag = True
            success(command)
        else:
            no_change(command)

        return ptt_flag

    def rf_ptt_off(self, command, ptt_flag):
        if self.rf_ptt.value != OFF:
            self.rf_ptt.off()
            ptt_flag = False
            success(command)
            #  set time ptt turned off
            self.ptt_off_time = datetime.now()
        else:
            no_change(command)

        return ptt_flag

    def pa_power_on(self, command):
        if self.pa_power.value != ON:
            #  Double-check the user wants to turn pa-power on
            if self.molly_guard(command):
                self.pa_power.on()
                success(command)
                self.dow_key_on(command)
        else:
            no_change(command)

    def pa_power_off(self, command):
        if self.pa_power.value != OFF:
            #  Check PTT off for at least 2 minutes
            if self.rf_ptt.value != OFF:
                print(Fore.RED + 'Cannot turn off pa-power while PTT is on.')
            else:
                diff_sec = self.calculate_ptt_off_time()
                if diff_sec > PTT_COOLDOWN:
                    self.pa_power.off()
                    success(command)
                    self.dow_key_off(command)
                else:
                    print(Fore.RED + 'Please wait {} seconds and try again.'.format(round(PTT_COOLDOWN - diff_sec)))
        else:
            no_change(command)

    def lna_on(self, command):
        #  Fail if PTT is on
        if self.rf_ptt.value == ON:
            print(Fore.RED + 'The LNA cannot be turned on while PTT is on for this band.')
            return

        if self.lna.value != ON:
            # Require inverse lna and dow-key states
            if self.dow_key.value == ON:
                self.dow_key_off(command)

            self.lna.on()
            success(command)
        else:
            no_change(command)

    def lna_off(self, command):
        if self.lna.value != OFF:
            self.lna.off()
            success(command)
            # If dow-key turned off for LNA, turn it back on
            if self.pa_power.value == ON and self.dow_key.value == OFF:
                self.dow_key_on(command)
        else:
            no_change(command)

    def polarization_left(self, command):
        if self.polarization.value != LEFT:
            #  Check ptt off for at least 100ms
            if self.rf_ptt.value != OFF:
                print(Fore.RED + 'Cannot change polarization while rf-ptt is on.')
            else:
                time.sleep(0.1)
                self.polarization.on()
                print(Fore.GREEN + 'Polarization for {} has successfully been set to {}'.format(command[0], command[2]))
        else:
            no_change(command)

    def polarization_right(self, command):
        if self.polarization.value != RIGHT:
            #  Check ptt off for at least 100ms
            if self.rf_ptt.value != OFF:
                print(Fore.RED + 'Cannot change polarization while rf-ptt is on.')
            else:
                time.sleep(0.1)
                self.polarization.off()
                print(Fore.GREEN + 'Polarization for {} has successfully been set to {}'.format(command[0], command[2]))
        else:
            no_change(command)


class VHF(Amplifier):
    def __init__(self):
        super().__init__()
        self.dow_key = DigitalOutputDevice(VHF_DOW_KEY, initial_value=False)
        self.rf_ptt = DigitalOutputDevice(VHF_RF_PTT, initial_value=False)
        self.pa_power = DigitalOutputDevice(VHF_PA_POWER, initial_value=False)
        self.lna = DigitalOutputDevice(VHF_LNA, initial_value=False)
        self.polarization = DigitalOutputDevice(VHF_POLARIZATION, initial_value=False)

        self.ptt_off_time = datetime.now()

    def command_parser(self, command, ptt_flag):
        match command:
            case['vhf', 'rf-ptt', 'on']:
                ptt_flag = self.rf_ptt_on(command, ptt_flag)
            case['vhf', 'rf-ptt', 'off']:
                ptt_flag = self.rf_ptt_off(command, ptt_flag)
            case['vhf', 'pa-power', 'on']:
                self.pa_power_on(command)
            case['vhf', 'pa-power', 'off']:
                self.pa_power_off(command)
            case['vhf', 'lna', 'on']:
                self.lna_on(command)
            case['vhf', 'lna', 'off']:
                self.lna_off(command)
            case['vhf', 'polarization', 'left']:
                self.polarization_left(command)
            case['vhf', 'polarization', 'right']:
                self.polarization_right(command)

        return ptt_flag


class UHF(Amplifier):
    def __init__(self):
        super().__init__()
        # self.dow_key = DigitalOutputDevice(UHF_DOW_KEY, initial_value=False)
        # self.rf_ptt = DigitalOutputDevice(UHF_RF_PTT, initial_value=False)
        # self.pa_power = DigitalOutputDevice(UHF_PA_POWER, initial_value=False)
        # self.lna = DigitalOutputDevice(UHF_LNA, initial_value=False)
        # self.polarization = DigitalOutputDevice(UHF_POLARIZATION, initial_value=False)

        self.ptt_time_off = datetime.now()

    def command_parser(self, command, ptt_flag):
        match command:
            case['uhf', 'rf-ptt', 'on']:
                ptt_flag = self.rf_ptt_on(command, ptt_flag)
            case['uhf', 'rf-ptt', 'off']:
                ptt_flag = self.rf_ptt_off(command, ptt_flag)
            case['uhf', 'pa-power', 'on']:
                self.pa_power_on(command)
            case['uhf', 'pa-power', 'off']:
                self.pa_power_off(command)
            case['uhf', 'lna', 'on']:
                self.lna_on(command)
            case['uhf', 'lna', 'off']:
                self.lna_off(command)
            case['uhf', 'polarization', 'left']:
                self.polarization_left(command)
            case['uhf', 'polarization', 'right']:
                self.polarization_right(command)

        return ptt_flag


class L_Band(Amplifier):
    def __init__(self):
        super().__init__()
        self.rf_ptt = DigitalOutputDevice(L_BAND_RF_PTT, initial_value=False)
        self.pa_power = DigitalOutputDevice(L_BAND_PA_POWER, initial_value=False)

        self.ptt_off_time = datetime.now()

    def command_parser(self, command, ptt_flag):
        match command:
            case['l-band', 'rf-ptt', 'on']:
                ptt_flag = self.rf_ptt_on(command, ptt_flag)
            case['l-band', 'rf-ptt', 'off']:
                ptt_flag = self.rf_ptt_off(command, ptt_flag)
            case['l-band', 'pa-power', 'on']:
                self.pa_power_on(command)
            case['l-band', 'pa-power', 'off']:
                self.pa_power_off(command)

        return ptt_flag


class Accessory:
    def __int__(self):
        self.power = None

    def power_on(self, command):
        if self.power.value != ON:
            self.power.on()
            success(command)
        else:
            no_change(command)

    def power_off(self, command):
        if self.power.value != OFF:
            self.power.off()
            success(command)
        else:
            no_change(command)


class RX_Swap(Accessory):
    def __init__(self):
        super().__init__()
        self.power = DigitalOutputDevice(RX_SWAP_POWER, initial_value=False)

    def command_parser(self, command, ptt_flag):
        if ptt_flag is True:
            print(Fore.RED + 'rx-swap cannot happen while PTT is active')
            return

        match command:
            case['rx-swap', 'power', 'on']:
                self.power_on(command)
            case['rx-swap', 'power', 'off']:
                self.power_off(command)


class SBC_Satnogs(Accessory):
    def __init__(self):
        super().__init__()
        self.power = DigitalOutputDevice(SBC_SATNOGS_POWER, initial_value=False)

    def command_parser(self, command):
        match command:
            case['sbc-satnogs', 'power', 'on']:
                self.power_on(command)
            case['sbd-satnogs', 'power', 'off']:
                self.power_off(command)


class SDR_Lime(Accessory):
    def __init__(self):
        super().__init__()
        self.power = DigitalOutputDevice(SDR_LIME_POWER, initial_value=False)

    def command_parser(self, command):
        match command:
            case['sdr-lime', 'power', 'on']:
                self.power_on(command)
            case['sdr-lime', 'power', 'off']:
                self.power_off(command)


class Rotator(Accessory):
    def __init__(self):
        super().__init__()
        self.power = DigitalOutputDevice(ROTATOR_POWER, initial_value=False)

    def command_parser(self, command):
        match command:
            case['rotator', 'power', 'on']:
                self.power_on(command)
            case['rotator', 'power', 'off']:
                self.power_off(command)


class StationD:
    def __init__(self):
        # TO-DO: get status of devices on initialization

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

    def command_listener(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((UDP_IP, UDP_PORT))

        while True:
            #  Get plain-language commands from the user
            # command = input(Fore.BLUE + 'command: ' + Fore.RESET).split()
            data, addr = sock.recvfrom(1024)
            command = data.decode().strip('\n').split()
            device = command[0]

            match device:
                case 'vhf':
                    self.ptt_flag = self.vhf.command_parser(command, self.ptt_flag)
                case 'uhf':
                    self.ptt_flag = self.uhf.command_parser(command, self.ptt_flag)
                case 'l-band':
                    self.ptt_flag = self.l_band.command_parser(command, self.ptt_flag)
                case 'rx-swap':
                    self.rx_swap.command_parser(command, self.ptt_flag)
                case 'sbc-satnogs':
                    self.sbc_satnogs.command_parser(command)
                case 'sdr-lime':
                    self.sdr_lime.command_parser(command)
                case 'rotator':
                    self.rotator.command_parser(command)
                case _:
                    match command:
                        case['exit']:
                            break
                        case _:
                            print(Fore.RED + 'Invalid command')


def success(command):
    print(Fore.GREEN + '{} has successfully been turned {} for {}'.format(command[1], command[2], command[0]))


def no_change(command):
    print(Fore.YELLOW + '{} is already {} for {}.'.format(command[1], command[2], command[0]))


def main():
    sd = StationD()
    sd.command_listener()


if __name__ == "__main__":
    print('====================================================')
    print('Station Daemon Power Management')
    print('====================================================')

    main()
