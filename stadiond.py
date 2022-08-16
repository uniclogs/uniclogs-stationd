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

    def run(self):
        while(True):
            #  Get plain-language commands from the user
            command = input('command: ').split()
            match command:
                case ['power-on', 'device']:
                    # get status, check if legal, UDP stuff
                    guard = input('Are you sure you want to {} {}? y/n: '.format(command[0], command[1]))
                    if guard == 'y':
                        # do GPIO stuff
                        print('Turned on {}'.format(command[1]))
                case ['status']:
                    # Get system status
                    self.get_system_status()
                case['status', 'device']:
                    # get device status
                    pass
                case ['exit']:
                    print('Exiting the program')
                    break
                case _:
                    print('Invalid command')



if __name__ == "__main__":
    print('====================================================')
    print('Station D Power Management')
    print('====================================================')

    sd = StationD()
    sd.run()


