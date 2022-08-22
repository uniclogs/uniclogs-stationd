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

VHF_DOW_KEY = 17            # pin 11
VHF_RF_PTT = 18             # pin 12
VHF_PA_POWER = 27           # pin 13
VHF_LNA = 22                # pin 15
VHF_POLARIZATION = 23       # pin 16

# UHF_DOW_KEY = 0
# UHF_RF_PTT = 0
# UHF_PA_POWER = 0
# UHF_LNA = 0
# UHF_POLARIZATION = 0

L_BAND_RF_PTT = 24          # pin 18
L_BAND_PA_POWER = 25        # pin 22

S_BAND_POWER = 11           # pin 23

OTHER_CONTROL = 8           # pin 24

ON = 1
OFF = 0
PTT_COOLDOWN = 120          # In seconds


class Device:
    def __init__(self, name, power_status, temperature):
        self.name = name
        self.power_status = power_status
        self.temperature = temperature


class StationD:
    def __init__(self):
        # TO-DO: get status of devices on initialization

        # VHF Devices
        self.vhf_dow_key = DigitalOutputDevice(VHF_DOW_KEY, initial_value=False)
        self.vhf_rf_ptt = DigitalOutputDevice(VHF_RF_PTT, initial_value=False)
        self.vhf_pa_power = DigitalOutputDevice(VHF_PA_POWER, initial_value=False)
        self.vhf_lna = DigitalOutputDevice(VHF_LNA, initial_value=False)
        self.vhf_polarization = DigitalOutputDevice(VHF_POLARIZATION, initial_value=False)

        # # UHF Devices
        # self.uhf_dow_key = DigitalOutputDevice(UHF_DOW_KEY, initial_value=False)
        # self.uhf_rf_ptt = DigitalOutputDevice(UHF_RF_PTT, initial_value=False)
        # self.uhf_pa_power = DigitalOutputDevice(UHF_PA_POWER, initial_value=False)
        # self.uhf_lna = DigitalOutputDevice(UHF_LNA, initial_value=False)
        # self.uhf_polarization = DigitalOutputDevice(UHF_POLARIZATION, initial_value=False)

        # L-Band Devices
        self.l_band_rf_ptt = DigitalOutputDevice(L_BAND_RF_PTT, initial_value=False)
        self.l_band_pa_power = DigitalOutputDevice(L_BAND_PA_POWER, initial_value=False)

        # S-Band Devices
        self.s_band_power = DigitalOutputDevice(S_BAND_POWER, initial_value=False)

        # Other Devices
        self.other_control = DigitalOutputDevice(OTHER_CONTROL, initial_value=False)

        #
        self.vhf_ptt_off_time = datetime.now()
        self.uhf_ptt_off_time = datetime.now()

    def get_system_status(self):
        # get status for all devices
        pass

    def get_device_status(self, device):
        # get status for one device
        pass

    @staticmethod
    def no_change(command):
        print('{} is already {} for {}.'.format(command[1], command[2], command[0]))

    @staticmethod
    def molly_guard(command):
        answer = input('Are you sure you want to turn {} {} for {}? y/n: '.format(command[1], command[2], command[0]))
        if answer.lower() == 'y':
            return True
        else:
            return False

    def calculate_ptt_off_time(self, band):
        print('in diff calc')
        print(band)
        now = datetime.now()
        print (now)
        if band == 'vhf':
            vhf_diff = now - self.vhf_ptt_off_time
            vhf_diff_sec = vhf_diff.total_seconds()
            print(vhf_diff)
            print(vhf_diff_sec)
            return vhf_diff_sec
        elif band == 'uhf':
            uhf_diff = now - self.uhf_ptt_off_time
            uhf_diff_sec = uhf_diff.total_seconds()
            return uhf_diff_sec

    def vhf_command(self, command):
        band = command[0]
        component = command[1]
        match command:
            case ['vhf', 'dow-key', 'on']:
                if self.vhf_dow_key.value != ON:
                    self.vhf_dow_key.on()
                else:
                    self.no_change(command)
            case ['vhf', 'dow-key', 'off']:
                if self.vhf_dow_key.value != OFF:
                    self.vhf_dow_key.off()
                else:
                    self.no_change(command)
            case ['vhf', 'rf-ptt', 'on']:
                if self.vhf_rf_ptt.value != ON:
                    #  Turn off Lna, cool down before turning on ptt
                    if self.vhf_lna.value != OFF:
                        self.vhf_lna.off()
                        time.sleep(0.1)
                    self.vhf_rf_ptt.on()
                else:
                    self.no_change(command)
            case ['vhf', 'rf-ptt', 'off']:
                if self.vhf_rf_ptt.value != OFF:
                    self.vhf_rf_ptt.off()
                    #  set time ptt turned off
                    self.vhf_ptt_off_time = datetime.now()
                    print(self.vhf_ptt_off_time)
                else:
                    self.no_change(command)
            case ['vhf', 'pa-power', 'on']:
                if self.vhf_pa_power.value != ON:
                    #  Double-check the user wants to turn pa-power on
                    if self.molly_guard(command):
                        self.vhf_pa_power.on()
                else:
                    self.no_change(command)
            case ['vhf', 'pa-power', 'off']:
                if self.vhf_pa_power.value != OFF:
                    #  Check PTT off for at least 2 minutes
                    if self.vhf_rf_ptt.value != OFF:
                        print('Cannot turn off {} while PTT is on.'.format(component))
                    else:
                        diff_sec = self.calculate_ptt_off_time(band)
                        if diff_sec > PTT_COOLDOWN:
                            self.vhf_pa_power.off()
                        else:
                            print('Please wait {} seconds and try again.'.format(PTT_COOLDOWN - diff_sec))
                else:
                    self.no_change(command)
            case ['vhf', 'lna', 'on']:
                if self.vhf_lna.value != ON:
                    #  Fail if PTT is on
                    if self.vhf_rf_ptt.value != OFF:
                        print('The LNA cannot be turned on while PTT is on for this band.')
                    else:
                        self.vhf_lna.on()
                else:
                    self.no_change(command)
            case ['vhf', 'lna', 'off']:
                if self.vhf_lna.value != OFF:
                    self.vhf_lna.off()
                else:
                    self.no_change(command)
            case ['vhf', 'polarization', 'on']:
                if self.vhf_polarization.value != ON:
                    #  Check ptt off for at least 100ms
                    if self.vhf_rf_ptt.value != OFF:
                        print('Cannot change polarization while rf-ptt is on.')
                    else:
                        time.sleep(0.1)
                        self.vhf_polarization.on()
                else:
                    self.no_change(command)
            case ['vhf', 'polarization', 'off']:
                if self.vhf_polarization.value != OFF:
                    #  Check ptt off for at least 100ms
                    if self.vhf_rf_ptt != OFF:
                        print('Cannot change polarization while rf-ptt is on.')
                    else:
                        time.sleep(0.1)
                        self.vhf_polarization.off()
                else:
                    self.no_change(command)
            case _:
                print('Invalid command')

    def uhf_command(self, command):
        match command:
            case ['uhf', 'dow-key', 'on']:
                pass
            case ['uhf', 'dow-key', 'off']:
                pass
            case ['uhf', 'rf-ptt', 'on']:
                pass
            case ['uhf', 'rf-ptt', 'off']:
                pass
            case ['uhf', 'pa-power', 'on']:
                pass
            case ['uhf', 'pa-power', 'off']:
                pass
            case ['uhf', 'lna', 'on']:
                pass
            case ['uhf', 'lna', 'off']:
                pass
            case ['uhf', 'polarization', 'on']:
                pass
            case ['uhf', 'polarization', 'off']:
                pass
            case _:
                pass

    def l_band_command(self, command):
        match command:
            case ['l-band', 'rf-ptt', 'on']:
                if self.l_band_rf_ptt.value != ON:
                    self.l_band_rf_ptt.on()
                else:
                    self.no_change(command)
            case ['l-band', 'rf-ptt', 'off']:
                if self.l_band_rf_ptt.value != OFF:
                    self.l_band_rf_ptt.off()
                else:
                    self.no_change(command)
            case ['l-band', 'pa-power', 'on']:
                if self.l_band_pa_power.value != ON:
                    self.l_band_pa_power.on()
                else:
                    self.no_change(command)
            case ['l-band', 'pa-power', 'off']:
                if self.l_band_pa_power.value != OFF:
                    self.l_band_pa_power.off()
                else:
                    self.no_change(command)
            case _:
                print('Invalid command')

    def s_band_command(self, command):
        match command:
            case ['s-band', 'power', 'on']:
                if self.s_band_power.value != ON:
                    self.s_band_power.on()
                else:
                    self.no_change(command)
            case ['s-band', 'power', 'off']:
                if self.s_band_power.value != OFF:
                    self.s_band_power.off()
                else:
                    self.no_change(command)
            case _:
                print('Invalid command')

    def other_control_command(self, command):
        match command:
            case ['other', 'power', 'on']:
                if self.other_control.value != ON:
                    self.other_control.on()
                else:
                    self.no_change(command)
            case ['other', 'power', 'off']:
                if self.other_control.value != OFF:
                    self.other_control.off()
                else:
                    self.no_change(command)
            case _:
                print('Invalid command')

    def command_prompt(self):
        while True:
            #  Get plain-language commands from the user
            command = input('command: ').split()
            band = command[0]

            #  Band-Specific commands
            if band == 'vhf':
                self.vhf_command(command)
            elif band == 'uhf':
                self.uhf_command(command)
            elif band == 'l-band':
                self.l_band_command(command)
            elif band == 's-band':
                self.s_band_command(command)
            elif band == 'other':
                self.other_control_command(command)
            else:
                match command:
                    #  Non-band commands
                    case['exit']:
                        break
                    case _:
                        print('Invalid command')


def main():
    sd = StationD()
    sd.command_prompt()


if __name__ == "__main__":
    print('====================================================')
    print('Station D Power Management')
    print('====================================================')

    main()
