"""
Author: Steven Borrego
Date: Aug 2022

Station D Power management
"""

from gpiozero import DigitalOutputDevice
import socket
import logging
import time

VHF_DOW_KEY = 17            # pin 11
VHF_RF_PTT = 18             # pin 12
VHF_PA_POWER = 27           # pin 13
VHF_LNA = 22                # pin 15
VHF_POLARIZATION = 23       # pin 16

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

    def get_system_status(self):
        # get status for all devices
        pass

    def get_device_status(self, device):
        # get status for one device
        pass

    def power_on_device(self, device):
        pass

    def run(self):
        while True:
            #  Get plain-language commands from the user
            command = input('command: ').split()
            match command:
                # # Generic device case
                # case ['power-on', 'device']:
                #     # get status, check if legal, UDP stuff
                #     guard = input('Are you sure you want to {} {}? y/n: '.format(command[0], command[1]))
                #     if guard == 'y':
                #         # do GPIO stuff
                #         print('Turned on {}'.format(command[1]))
                # case ['status']:
                #     # Get system status
                #     self.get_system_status()
                # case ['status', 'device']:
                #     # get device status
                #     pass
                # case ['exit']:
                #     print('Exiting the program')
                #     break

                #  VHF Band Commands
                case ['vhf', 'dow-key', 'on']:
                    self.vhf_dow_key.on()
                case ['vhf', 'dow-key', 'off']:
                    self.vhf_dow_key.off()
                case ['vhf', 'rf-ptt', 'on']:
                    #  Turn off Lna, cool down before turning on
                    self.vhf_rf_ptt.on()
                case ['vhf', 'rf-ptt', 'off']:
                    self.vhf_rf_ptt.off()
                case ['vhf', 'pa-power', 'on']:
                    self.vhf_pa_power.on()
                case ['vhf', 'pa-power', 'off']:
                    self.vhf_pa_power.off()
                case ['vhf', 'lna', 'on']:
                    #  Fail if PTT is on
                    self.vhf_lna.on()
                case ['vhf', 'lna', 'off']:
                    self.vhf_lna.off()
                case ['vhf', 'polarization', 'on']:
                    self.vhf_polarization.on()
                case ['vhf', 'polarization', 'off']:
                    self.vhf_polarization.off()

                #  UHF Band Commands
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

                #  L-Band Commands
                case ['l-band', 'rf-ptt', 'on']:
                    pass
                case ['l-band', 'rf-ptt', 'off']:
                    pass
                case ['l-band', 'pa-power', 'on']:
                    pass
                case ['l-band', 'pa-power', 'off']:
                    pass

                #  S-Band Commands
                case ['S-band', 'power', 'on']:
                    pass
                case ['s-band', 'power', 'off']:
                    pass

                #  Other Control (SDRs, Rotator)
                case ['other', 'power', 'on']:
                    pass
                case ['other', 'power', 'off']:
                    pass

                case _:
                    print('Invalid command')


def main():
    sd = StationD()
    sd.run()

if __name__ == "__main__":
    print('====================================================')
    print('Station D Power Management')
    print('====================================================')

    main()

