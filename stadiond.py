"""
Author: Steven Borrego
Date: Aug 2022

Station D Power management
"""

import gpiozero
import socket
import logging
import time


class Device:
    def __init__(self, name, power_status, temperature):
        self.name = name
        self.power_status = power_status
        self.temperature = temperature


class StationD:
    def __init__(self):
        # get status of devices on initialization
        pass

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
                    if gpiozero.DigitalOutputDevice(7).value != 1:
                        gpiozero.DigitalOutputDevice(7).on()
                    else:
                        print('{} {} is already on.'.format(command[0], command[1]))
                case ['vhf', 'dow-key', 'off']:
                    if gpiozero.DigitalOutputDevice(7).value != 0:
                        gpiozero.DigitalOutputDevice(7).off()
                    else:
                        print('{} {} is already off.'.format(command[0], command[1]))
                case ['vhf', 'rf-ptt', 'on']:
                    #  Turn off Lna, cool down before turning on
                    pass
                case ['vhf', 'rf-ptt', 'off']:
                    pass
                case ['vhf', 'pa-power', 'on']:
                    pass
                case ['vhf', 'pa-power', 'off']:
                    pass
                case ['vhf', 'lna', 'on']:
                    #  Fail if PTT is on
                    pass
                case ['vhf', 'lna', 'off']:
                    pass
                case ['vhf', 'polarization', 'on']:
                    pass
                case ['vhf', 'polarization', 'off']:
                    pass

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


if __name__ == "__main__":
    print('====================================================')
    print('Station D Power Management')
    print('====================================================')

    sd = StationD()
    sd.run()
