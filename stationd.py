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

# UHF_DOW_KEY = 0
# UHF_RF_PTT = 0
# UHF_PA_POWER = 0
# UHF_LNA = 0
# UHF_POLARIZATION = 0
#
# L_BAND_RF_PTT = 0
# L_BAND_PA_POWER = 0
#
# S_BAND_POWER = 0
#
# OTHER_CONTROL = 0

ON = 1
OFF = 0


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
        #
        # # L-Band Devices
        # self.l_band_rf_ptt = DigitalOutputDevice(L_BAND_RF_PTT, initial_value=False)
        # self.l_band_pa_power = DigitalOutputDevice(L_BAND_PA_POWER, initial_value=False)
        #
        # # S-Band Devices
        # self.s_band_power = DigitalOutputDevice(S_BAND_POWER, initial_value=False)
        #
        # # Other Devices
        # self.other_control = DigitalOutputDevice(OTHER_CONTROL, initial_value=False)

    def get_system_status(self):
        # get status for all devices
        pass

    def get_device_status(self, device):
        # get status for one device
        pass

    def power_on_device(self, command):
        pass

    def power_off_device(self, command):
        pass

    def command_prompt(self):
        while True:
            #  Get plain-language commands from the user
            command = input('command: ').split()

            #  TO-DO: Break out on/off logic to generic methods
            match command:
                #  VHF Band Commands
                case ['vhf', 'dow-key', 'on']:
                    if self.vhf_dow_key.value != ON:
                        self.vhf_dow_key.on()
                    else:
                        print('{} {} is already on'.format(command[0], command[1]))
                case ['vhf', 'dow-key', 'off']:
                    if self.vhf_dow_key.value != OFF:
                        self.vhf_dow_key.off()
                    else:
                        print('{} {} is already off'.format(command[0], command[1]))
                case ['vhf', 'rf-ptt', 'on']:
                    #  Turn off Lna, cool down before turning on ptt
                    if self.vhf_rf_ptt.value != ON:
                        if self.vhf_lna.value != OFF:
                            self.vhf_lna.off()
                            time.sleep(0.1)
                            #  Cool down period
                        self.vhf_rf_ptt.on()
                    else:
                        print('{} {} is already on'.format(command[0], command[1]))
                case ['vhf', 'rf-ptt', 'off']:
                    if self.vhf_rf_ptt.value != OFF:
                        self.vhf_rf_ptt.off()
                        #  TO-DO: Log time ptt has been off
                    else:
                        print('{} {} is already off'.format(command[0], command[1]))
                case ['vhf', 'pa-power', 'on']:
                    if self.vhf_pa_power.value != ON:
                        self.vhf_pa_power.on()
                    else:
                        print('{} {} is already on'.format(command[0], command[1]))
                case ['vhf', 'pa-power', 'off']:
                    if self.vhf_pa_power.value != OFF:
                        self.vhf_pa_power.off()
                    else:
                        print('{} {} is already off'.format(command[0], command[1]))
                case ['vhf', 'lna', 'on']:
                    #  Fail if PTT is on
                    if self.vhf_lna.value != ON:
                        if self.vhf_rf_ptt.value != OFF:
                            print('The LNA cannot be turned on while PTT is on for this band.')
                        else:
                            self.vhf_lna.on()
                    else:
                        print('{} {} is already on'.format(command[0], command[1]))
                case ['vhf', 'lna', 'off']:
                    if self.vhf_lna.value != OFF:
                        self.vhf_lna.off()
                    else:
                        print('{} {} is already off'.format(command[0], command[1]))
                case ['vhf', 'polarization', 'on']:
                    if self.vhf_polarization.value != ON:
                        self.vhf_polarization.on()
                    else:
                        print('{} {} is already on'.format(command[0], command[1]))
                case ['vhf', 'polarization', 'off']:
                    if self.vhf_polarization.value != OFF:
                        self.vhf_polarization.off()
                    else:
                        print('{} {} is already off'.format(command[0], command[1]))

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
