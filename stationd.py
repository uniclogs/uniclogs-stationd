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

# UHF_DOW_KEY = 17
# UHF_RF_PTT = 18
# UHF_PA_POWER = 27
# UHF_LNA = 22
# UHF_POLARIZATION = 23

L_BAND_RF_PTT = 24          # pin 18
L_BAND_PA_POWER = 25        # pin 22

S_BAND_RX_SWAP = 11         # pin 23

SDR_ROCK_POWER = 8          # pin 24
LIME_SDR_POWER = 2          # pin 29
ROTATOR_POWER = 6           # pin 31

ON = 1
OFF = 0
PTT_COOLDOWN = 120          # In seconds


class Device:
    def __init__(self):
        # VHF, UHF, L-Band
        self.dow_key = None
        self.rf_ptt = None
        self.pa_power = None
        self.lna = None
        self.polarization = None

        self.ptt_off_time = None

        # Other Control
        self.power = None

    @staticmethod
    def molly_guard(command):
        answer = input('Are you sure you want to turn {} {} for {}? y/n: '.format(command[1], command[2], command[0]))
        if answer.lower() == 'y':
            return True
        else:
            return False

    @staticmethod
    def no_change(command):
        print('{} is already {} for {}.'.format(command[1], command[2], command[0]))

    def calculate_ptt_off_time(self):
        now = datetime.now()
        diff = now - self.ptt_off_time
        diff_sec = diff.total_seconds()

        return diff_sec

    def dow_key_on(self, command):
        if self.dow_key.value != ON:
            self.dow_key.on()
        else:
            self.no_change(command)

    def dow_key_off(self, command):
        if self.dow_key.value != OFF:
            self.dow_key.off()
        else:
            self.no_change(command)

    def rf_ptt_on(self, command):
        if self.rf_ptt.value != ON:
            #  Turn off Lna, cool down before turning on ptt
            if self.lna.value != OFF:
                self.lna.off()
                time.sleep(0.1)
            self.rf_ptt.on()
        else:
            self.no_change(command)

    def rf_ptt_off(self, command):
        if self.rf_ptt.value != OFF:
            self.rf_ptt.off()
            #  set time ptt turned off
            self.ptt_off_time = datetime.now()
        else:
            self.no_change(command)

    def pa_power_on(self, command):
        if self.pa_power.value != ON:
            #  Double-check the user wants to turn pa-power on
            if self.molly_guard(command):
                self.pa_power.on()
        else:
            self.no_change(command)

    def pa_power_off(self, command):
        if self.pa_power.value != OFF:
            #  Check PTT off for at least 2 minutes
            if self.rf_ptt.value != OFF:
                print('Cannot turn off pa-power while PTT is on.')
            else:
                diff_sec = self.calculate_ptt_off_time()
                if diff_sec > PTT_COOLDOWN:
                    self.pa_power.off()
                else:
                    print('Please wait {} seconds and try again.'.format(round(PTT_COOLDOWN - diff_sec)))
        else:
            self.no_change(command)

    def lna_on(self, command):
        if self.lna.value != ON:
            #  Fail if PTT is on
            if self.rf_ptt.value != OFF:
                print('The LNA cannot be turned on while PTT is on for this band.')
            else:
                self.lna.on()
        else:
            self.no_change(command)

    def lna_off(self, command):
        if self.lna.value != OFF:
            self.lna.off()
        else:
            self.no_change(command)

    def polarization_on(self, command):
        if self.polarization.value != ON:
            #  Check ptt off for at least 100ms
            if self.rf_ptt.value != OFF:
                print('Cannot change polarization while rf-ptt is on.')
            else:
                time.sleep(0.1)
                self.polarization.on()
        else:
            self.no_change(command)

    def polarization_off(self, command):
        if self.polarization.value != OFF:
            #  Check ptt off for at least 100ms
            if self.rf_ptt != OFF:
                print('Cannot change polarization while rf-ptt is on.')
            else:
                time.sleep(0.1)
                self.polarization.off()
        else:
            self.no_change(command)

    def power_on(self, command):
        if self.power.value != ON:
            self.power.on()
        else:
            self.no_change(command)

    def power_off(self, command):
        if self.power.value != OFF:
            self.power.off()
        else:
            self.no_change(command)


class VHF(Device):
    def __int__(self):
        self.dow_key = DigitalOutputDevice(VHF_DOW_KEY, initial_value=False)
        self.rf_ptt = DigitalOutputDevice(VHF_RF_PTT, initial_value=False)
        self.pa_power = DigitalOutputDevice(VHF_PA_POWER, initial_value=False)
        self.lna = DigitalOutputDevice(VHF_LNA, initial_value=False)
        self.polarization = DigitalOutputDevice(VHF_POLARIZATION, initial_value=False)


class UHF(Device):
    def __int__(self):
        # self.dow_key = DigitalOutputDevice(UHF_DOW_KEY, initial_value=False)
        # self.rf_ptt = DigitalOutputDevice(UHF_RF_PTT, initial_value=False)
        # self.pa_power = DigitalOutputDevice(UHF_PA_POWER, initial_value=False)
        # self.lna = DigitalOutputDevice(UHF_LNA, initial_value=False)
        # self.polarization = DigitalOutputDevice(UHF_POLARIZATION, initial_value=False)
        pass


class L_Band(Device):
    def __int__(self):
        self.rf_ptt = DigitalOutputDevice(L_BAND_RF_PTT, initial_value=False)
        self.pa_power = DigitalOutputDevice(L_BAND_PA_POWER, initial_value=False)


class S_Band(Device):
    def __int__(self):
        self.rx_swap = DigitalOutputDevice(S_BAND_RX_SWAP, initial_value=False)

    def rx_swap_on(self, command):
        if self.rx_swap.value != ON:
            self.rx_swap.on()
        else:
            self.no_change(command)

    def rx_swap_off(self, command):
        if self.rx_swap.value != OFF:
            self.rx_swap.off()
        else:
            self.no_change(command)


class SDR_Rock(Device):
    def __int__(self):
        self.power = DigitalOutputDevice(SDR_ROCK_POWER, initial_value=False)


class Lime_SDR(Device):
    def __int__(self):
        self.power = DigitalOutputDevice(LIME_SDR_POWER, initial_value=False)


class Rotator(Device):
    def __int__(self):
        self.power = DigitalOutputDevice(ROTATOR_POWER, initial_value=False)


class StationD:
    def __init__(self):
        # TO-DO: get status of devices on initialization
        self.vhf = VHF()
        self.uhf = UHF()
        self.l_band = L_Band()
        self.s_band = S_Band()
        self.sdr_rock = SDR_Rock()
        self.lime_sdr = Lime_SDR()
        self.rotator = Rotator()

    def command_prompt(self):
        while True:
            #  Get plain-language commands from the user
            command = input('command: ').split()

            match command:
                # VHF Commands
                case ['vhf', 'dow-key', 'on']:
                    self.vhf.dow_key_on(command)
                case ['vhf', 'dow-key', 'off']:
                    self.vhf.dow_key_off(command)
                case ['vhf', 'rf-ptt', 'on']:
                    self.vhf.rf_ptt_on(command)
                case ['vhf', 'rf-ptt', 'off']:
                    self.vhf.rf_ptt_off(command)
                case ['vhf', 'pa-power', 'on']:
                    self.vhf.pa_power_on(command)
                case ['vhf', 'pa-power', 'off']:
                    self.vhf.pa_power_off(command)
                case ['vhf', 'lna', 'on']:
                    self.vhf.lna_on(command)
                case ['vhf', 'lna', 'off']:
                    self.vhf.lna_off(command)
                case ['vhf', 'polarization', 'on']:
                    self.vhf.polarization_on(command)
                case ['vhf', 'polarization', 'off']:
                    self.vhf.polarization_off(command)
                # UHF Commands
                case ['uhf', 'dow-key', 'on']:
                    self.uhf.dow_key_on(command)
                case ['uhf', 'dow-key', 'off']:
                    self.uhf.dow_key_off(command)
                case ['uhf', 'rf-ptt', 'on']:
                    self.uhf.rf_ptt_on(command)
                case ['uhf', 'rf-ptt', 'off']:
                    self.uhf.rf_ptt_off(command)
                case ['uhf', 'pa-power', 'on']:
                    self.uhf.pa_power_on(command)
                case ['uhf', 'pa-power', 'off']:
                    self.uhf.pa_power_off(command)
                case ['uhf', 'lna', 'on']:
                    self.uhf.lna_on(command)
                case ['uhf', 'lna', 'off']:
                    self.uhf.lna_off(command)
                case ['uhf', 'polarization', 'on']:
                    self.uhf.polarization_on(command)
                case ['uhf', 'polarization', 'off']:
                    self.uhf.polarization_off(command)
                # L-Band Commands
                case ['l-band', 'rf-ptt', 'on']:
                    self.l_band.rf_ptt_on(command)
                case ['l-band', 'rf-ptt', 'off']:
                    self.l_band.rf_ptt_off(command)
                case ['l-band', 'pa-power', 'on']:
                    self.l_band.pa_power_on(command)
                case ['l-band', 'pa-power', 'off']:
                    self.l_band.pa_power_off(command)
                # S-Band Commands
                case ['s-band', 'rx-swap', 'on']:
                    self.s_band.rx_swap_on(command)
                case ['s-band', 'rx-swap', 'off']:
                    self.s_band.rx_swap_off(command)
                # Other Control
                case ['sdr-rock', 'power', 'on']:
                    self.sdr_rock.power_on(command)
                case ['sdr-rock', 'power', 'off']:
                    self.sdr_rock.power_off(command)
                case ['lime-sdr', 'power', 'on']:
                    self.lime_sdr.power_on(command)
                case ['lime-sdr', 'power', 'off']:
                    self.lime_sdr.power_off(command)
                case ['rotator', 'power', 'on']:
                    self.rotator.power_on(command)
                case ['rotator', 'power', 'off']:
                    self.rotator.power_off(command)
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
