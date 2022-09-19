"""
Author: Steven Borrego
Date: Aug 2022

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

ON = 1
OFF = 0
PTT_COOLDOWN = 120          # In seconds

LEFT = 1
RIGHT = 0

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

    def status(self, command_obj):
        status = {}
        # Dow-key
        if self.dow_key is not None:
            status.update({'dow-key': 'ON'}) if self.dow_key.read() is ON else status.update({'dow-key': 'OFF'})
        else:
            status.update({'dow-key': 'N/A'})
        # Pa-Power
        if self.pa_power is not None:
            status.update({'pa-power': 'ON'}) if self.pa_power.read() is ON else status.update({'pa-power': 'OFF'})
        else:
            status.update({'pa-power': 'N/A'})
        # PTT
        if self.rf_ptt is not None:
            status.update({'rf-ptt': 'ON'}) if self.rf_ptt.read() is ON else status.update({'rf-ptt': 'OFF'})
        else:
            status.update({'rf-ptt': 'N/A'})
        # LNA
        if self.lna is not None:
            status.update({'lna': 'ON'}) if self.lna.read() is ON else status.update({'lna': 'OFF'})
        else:
            status.update({'lna': 'N/A'})
        # Polarization
        if self.polarization is not None:
            status.update({'polarization': 'LEFT'}) if self.polarization.read() == 1 \
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

    def component_status(self, command_obj):
        component = command_obj.command[1]
        try:
            match component:
                case 'dow-key':
                    if self.dow_key is None:
                        raise No_Component

                    message = 'ON\n' if self.dow_key.read() is ON else 'OFF\n'
                    command_obj.send_response(message)
                case 'rf-ptt':
                    if self.rf_ptt is None:
                        raise No_Component

                    message = 'ON\n' if self.rf_ptt.read() is ON else 'OFF\n'
                    command_obj.send_response(message)
                case 'pa-power':
                    if self.pa_power is None:
                        raise No_Component

                    message = 'ON\n' if self.pa_power.read() is ON else 'OFF\n'
                    command_obj.send_response(message)
                case 'lna':
                    if self.lna is None:
                        raise No_Component

                    message = 'ON\n' if self.lna.read() is ON else 'OFF\n'
                    command_obj.send_response(message)
                case 'polarization':
                    if self.polarization is None:
                        raise No_Component

                    message = 'LEFT\n' if self.polarization.read() is ON else 'RIGHT\n'
                    command_obj.send_response(message)
        except No_Component:
            message = f'FAIL: {component} No Component\n'
            command_obj.send_response(message)
        except Exception as error:
            print(error)

    def molly_guard(self, command_obj):
        # first request
        if self.molly_guard_time is None:
            # set timer
            self.molly_guard_time = datetime.now()
            command_obj.molly_guard_response()
            return False

        # subsequent requests
        now = datetime.now()
        diff = now - self.molly_guard_time
        diff_sec = diff.total_seconds()
        if diff_sec > 20:
            # took too long
            self.molly_guard_time = datetime.now()  # reset timer
            command_obj.molly_guard_response()
            return False
        else:
            # reset timer to none
            self.molly_guard_time = None
            return True

    def calculate_ptt_off_time(self):
        # TO-DO: Overflow guard?
        now = datetime.now()
        diff = now - self.shared['ptt_off_time']
        diff_sec = diff.total_seconds()
        return diff_sec

    def dow_key_on(self, command_obj):
        try:
            if self.dow_key.read() is ON:
                raise Redundant_Request
            # Fail if PTT is on
            if self.rf_ptt.read() is ON:
                raise PTT_Conflict

            self.dow_key.write(gpio.HIGH)
            message = f'SUCCESS: {command_obj.command[0]} dow-key on\n'
            logging.debug(f'{str(datetime.now())} {message.strip()}, ADDRESS: {str(command_obj.addr)}')
            command_obj.send_response(message)
        except Redundant_Request:
            message = f'WARNING: {command_obj.command[0]} dow-key on No Change\n'
            logging.debug(f'{str(datetime.now())} {message.strip()}, ADDRESS: {str(command_obj.addr)}')
            command_obj.send_response(message)
        except PTT_Conflict:
            command_obj.ptt_conflict_response()
        except Exception as error:
            print(error)

    def dow_key_off(self, command_obj):
        try:
            if self.dow_key.read() is OFF:
                raise Redundant_Request
            # Fail if PTT is on
            if self.rf_ptt.read() is ON:
                raise PTT_Conflict

            self.dow_key.write(gpio.LOW)
            message = f'SUCCESS: {command_obj.command[0]} dow-key off\n'
            logging.debug(f'{str(datetime.now())} {message.strip()}, ADDRESS: {str(command_obj.addr)}')
            command_obj.send_response(message)
        except Redundant_Request:
            message = f'WARNING: {command_obj.command[0]} dow-key off No Change\n'
            logging.debug(f'{str(datetime.now())} {message.strip()}, ADDRESS: {str(command_obj.addr)}')
            command_obj.send_response(message)
        except PTT_Conflict:
            command_obj.ptt_conflict_response()
        except Exception as error:
            print(error)

    def rf_ptt_on(self, command_obj, num_active_ptt):
        try:
            if self.rf_ptt.read() is ON:
                raise Redundant_Request
            if self.pa_power.read() is OFF:
                raise PTT_Conflict
            if num_active_ptt == PTT_MAX_COUNT:
                raise Max_PTT

            #  Turn off Lna, cool down before turning on ptt
            if self.lna.read() is ON:
                self.lna.write(gpio.LOW)
                message = f'SUCCESS: {command_obj.command[0]} lna off\n'
                logging.debug(f'{str(datetime.now())} {message.strip()}, ADDRESS: {str(command_obj.addr)}')
                command_obj.send_response(message)
                time.sleep(0.1)

            self.rf_ptt.write(gpio.HIGH)
            num_active_ptt += 1
            command_obj.success_response()
        except Redundant_Request:
            command_obj.no_change_response()
        except PTT_Conflict:
            command_obj.ptt_conflict_response()
        except Max_PTT:
            message = 'FAIL: Max PTT\n'
            command_obj.send_response(message)
        except Exception as error:
            print(error)

        return num_active_ptt

    def rf_ptt_off(self, command_obj, num_active_ptt):
        try:
            if self.rf_ptt.read() is OFF:
                raise Redundant_Request

            self.rf_ptt.write(gpio.LOW)
            #  set time ptt turned off
            self.shared['ptt_off_time'] = datetime.now()
            num_active_ptt -= 1
            command_obj.success_response()
        except Redundant_Request:
            command_obj.no_change_response()
        except Exception as error:
            print(error)

        return num_active_ptt

    def pa_power_on(self, command_obj):
        try:
            if self.pa_power.read() is ON:
                raise Redundant_Request

            self.pa_power.write(gpio.HIGH)
            command_obj.success_response()

            if self.dow_key is not None:
                self.dow_key_on(command_obj)
        except Redundant_Request:
            command_obj.no_change_response()
        except Exception as error:
            print(error)

    def pa_power_off(self, command_obj):
        try:
            if self.pa_power.read() is OFF:
                raise Redundant_Request
            if self.rf_ptt.read() is ON:
                raise PTT_Conflict

            #  Check PTT off for at least 2 minutes
            if self.shared['ptt_off_time'] is None:
                self.pa_power.write(gpio.LOW)
                command_obj.success_response()

                if self.dow_key is not None:
                    self.dow_key_off(command_obj)
            else:
                diff_sec = self.calculate_ptt_off_time()
                if diff_sec > PTT_COOLDOWN:
                    self.pa_power.write(gpio.LOW)
                    command_obj.success_response()
                    if self.dow_key is not None:
                        self.dow_key_off(command_obj)
                else:
                    message = f'WARNING: Please wait {round(PTT_COOLDOWN - diff_sec)} seconds and try again.\n'
                    command_obj.send_response(message)
        except Redundant_Request:
            command_obj.no_change_response()
        except PTT_Conflict:
            command_obj.ptt_conflict_response()
        except Exception as error:
            print(error)

    def lna_on(self, command_obj):
        try:
            if self.lna.read() is ON:
                raise Redundant_Request
            #  Fail if PTT is on
            if self.rf_ptt.read() is ON:
                raise PTT_Conflict

            # Require inverse lna and dow-key states
            if self.dow_key.read() is ON:
                self.dow_key_off(command_obj)

            self.lna.write(gpio.HIGH)
            # self.lna.write(gpio.HIGH)
            command_obj.success_response()
        except Redundant_Request:
            command_obj.no_change_response()
        except PTT_Conflict:
            command_obj.ptt_conflict_response()
        except Exception as error:
            print(error)

    def lna_off(self, command_obj):
        try:
            if self.lna.read() is OFF:
                raise Redundant_Request

            self.lna.write(gpio.LOW)
            # self.lna.write(gpio.LOW)
            command_obj.success_response()

            # If dow-key turned off for LNA, turn it back on
            if self.pa_power.read() is ON and self.dow_key.read() is OFF:
                self.dow_key_on(command_obj)
        except Redundant_Request:
            command_obj.no_change_response()
        except Exception as error:
            print(error)

    def polarization_left(self, command_obj):
        try:
            if self.polarization.read() is LEFT:
                raise Redundant_Request
            if self.rf_ptt.read() is ON:
                raise PTT_Conflict

            time.sleep(0.1)
            self.polarization.write(gpio.HIGH)
            command_obj.success_response()
        except Redundant_Request:
            command_obj.no_change_response()
        except PTT_Conflict:
            command_obj.ptt_conflict_response()
        except Exception as error:
            print(error)

    def polarization_right(self, command_obj):
        try:
            if self.polarization.read() is RIGHT:
                raise Redundant_Request
            if self.rf_ptt.read() is ON:
                raise PTT_Conflict

            time.sleep(0.1)
            self.polarization.write(gpio.LOW)
            command_obj.success_response()
        except Redundant_Request:
            command_obj.no_change_response()
        except PTT_Conflict:
            command_obj.ptt_conflict_response()
        except Exception as error:
            print(error)


class VHF(Amplifier):
    def __init__(self):
        super().__init__()
        self.name = 'VHF'
        # Dow-key
        self.dow_key = gpio.GPIOPin(VHF_DOW_KEY, None, initial=None)
        print(f'GPIOPin object returned with value: {self.dow_key.read()}')
        if self.dow_key.get_direction() != gpio.OUT:
            print('Direction is not out. Setting.')
            self.dow_key.set_direction(gpio.OUT)
            print(f'value: {self.dow_key.read()}')
        if not self.dow_key.read():
            self.dow_key.write(gpio.LOW)
            print(f'Set value to {self.dow_key.read()}')
        # PTT
        self.rf_ptt = gpio.GPIOPin(VHF_RF_PTT, None, initial=None)
        print(f'GPIOPin object returned with value: {self.rf_ptt.read()}')
        if self.rf_ptt.get_direction() != gpio.OUT:
            print('Direction is not out. Setting.')
            self.rf_ptt.set_direction(gpio.OUT)
            print(f'value: {self.rf_ptt.read()}')
        if not self.rf_ptt.read():
            self.rf_ptt.write(gpio.LOW)
            print(f'Set value to {self.rf_ptt.read()}')
        # TX
        self.pa_power = gpio.GPIOPin(VHF_PA_POWER, None, initial=None)
        print(f'GPIOPin object returned with value: {self.pa_power.read()}')
        if self.pa_power.get_direction() != gpio.OUT:
            print('Direction is not out. Setting.')
            self.pa_power.set_direction(gpio.OUT)
            print(f'value: {self.pa_power.read()}')
        if not self.pa_power.read():
            self.pa_power.write(gpio.LOW)
            print(f'Set value to {self.pa_power.read()}')
        # RX
        self.lna = gpio.GPIOPin(VHF_LNA, None, initial=None)
        print(f'GPIOPin object returned with value: {self.lna.read()}')
        if self.lna.get_direction() != gpio.OUT:
            print('Direction is not out. Setting.')
            self.lna.set_direction(gpio.OUT)
            print(f'value: {self.lna.read()}')
        if not self.lna.read():
            self.lna.write(gpio.LOW)
            print(f'Set value to {self.lna.read()}')
        # Polarization
        self.polarization = gpio.GPIOPin(VHF_POLARIZATION, None, initial=None)
        print(f'GPIOPin object returned with value: {self.polarization.read()}')
        if self.polarization.get_direction() != gpio.OUT:
            print('Direction is not out. Setting.')
            self.polarization.set_direction(gpio.OUT)
            print(f'value: {self.polarization.read()}')
        if not self.polarization.read():
            self.polarization.write(gpio.LOW)
            print(f'Set value to {self.polarization.read()}')

    def command_parser(self, command_obj, num_active_ptt):
        match command_obj.command:
            case ['vhf', 'rf-ptt', 'on']:
                num_active_ptt = self.rf_ptt_on(command_obj, num_active_ptt)
            case ['vhf', 'rf-ptt', 'off']:
                num_active_ptt = self.rf_ptt_off(command_obj, num_active_ptt)
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
                self.status(command_obj)
            case _:
                command_obj.invalid_command_response()

        return num_active_ptt


class UHF(Amplifier):
    def __init__(self):
        super().__init__()
        self.name = 'UHF'
        # # Dow-key
        # self.dow_key = gpio.GPIOPin(UHF_DOW_KEY, None, initial=None)
        # print(f'GPIOPin object returned with value: {self.dow_key.read()}')
        # if self.dow_key.get_direction() != gpio.OUT:
        #     print('Direction is not out. Setting.')
        #     self.dow_key.set_direction(gpio.OUT)
        #     print(f'value: {self.dow_key.read()}')
        # if not self.dow_key.read():
        #     self.dow_key.write(gpio.LOW)
        #     print(f'Set value to {self.dow_key.read()}')
        # # PTT
        # self.rf_ptt = gpio.GPIOPin(UHF_RF_PTT, None, initial=None)
        # print(f'GPIOPin object returned with value: {self.rf_ptt.read()}')
        # if self.rf_ptt.get_direction() != gpio.OUT:
        #     print('Direction is not out. Setting.')
        #     self.rf_ptt.set_direction(gpio.OUT)
        #     print(f'value: {self.rf_ptt.read()}')
        # if not self.rf_ptt.read():
        #     self.rf_ptt.write(gpio.LOW)
        #     print(f'Set value to {self.rf_ptt.read()}')
        # # TX
        # self.pa_power = gpio.GPIOPin(UHF_PA_POWER, None, initial=None)
        # print(f'GPIOPin object returned with value: {self.pa_power.read()}')
        # if self.pa_power.get_direction() != gpio.OUT:
        #     print('Direction is not out. Setting.')
        #     self.pa_power.set_direction(gpio.OUT)
        #     print(f'value: {self.pa_power.read()}')
        # if not self.pa_power.read():
        #     self.pa_power.write(gpio.LOW)
        #     print(f'Set value to {self.pa_power.read()}')
        # # RX
        # self.lna = gpio.GPIOPin(UHF_LNA, None, initial=None)
        # print(f'GPIOPin object returned with value: {self.lna.read()}')
        # if self.lna.get_direction() != gpio.OUT:
        #     print('Direction is not out. Setting.')
        #     self.lna.set_direction(gpio.OUT)
        #     print(f'value: {self.lna.read()}')
        # if not self.lna.read():
        #     self.lna.write(gpio.LOW)
        #     print(f'Set value to {self.lna.read()}')
        # # Polarization
        # self.polarization = gpio.GPIOPin(UHF_POLARIZATION, None, initial=None)
        # print(f'GPIOPin object returned with value: {self.polarization.read()}')
        # if self.polarization.get_direction() != gpio.OUT:
        #     print('Direction is not out. Setting.')
        #     self.polarization.set_direction(gpio.OUT)
        #     print(f'value: {self.polarization.read()}')
        # if not self.polarization.read():
        #     self.polarization.write(gpio.LOW)
        #     print(f'Set value to {self.polarization.read()}')

    def command_parser(self, command_obj, num_active_ptt):
        match command_obj.command:
            case ['uhf', 'rf-ptt', 'on']:
                num_active_ptt = self.rf_ptt_on(command_obj, num_active_ptt)
            case ['uhf', 'rf-ptt', 'off']:
                num_active_ptt = self.rf_ptt_off(command_obj, num_active_ptt)
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
                self.status(command_obj)
            case _:
                command_obj.invalid_command_response()

        return num_active_ptt


class L_Band(Amplifier):
    def __init__(self):
        super().__init__()
        self.name = 'L-Band'

        # PTT
        self.rf_ptt = gpio.GPIOPin(L_BAND_RF_PTT, None, initial=None)
        print(f'GPIOPin object returned with value: {self.rf_ptt.read()}')
        if self.rf_ptt.get_direction() != gpio.OUT:
            print('Direction is not out. Setting.')
            self.rf_ptt.set_direction(gpio.OUT)
            print(f'value: {self.rf_ptt.read()}')
        if not self.rf_ptt.read():
            self.rf_ptt.write(gpio.LOW)
            print(f'Set value to {self.rf_ptt.read()}')
        # TX
        self.pa_power = gpio.GPIOPin(L_BAND_PA_POWER, None, initial=None)
        print(f'GPIOPin object returned with value: {self.pa_power.read()}')
        if self.pa_power.get_direction() != gpio.OUT:
            print('Direction is not out. Setting.')
            self.pa_power.set_direction(gpio.OUT)
            print(f'value: {self.pa_power.read()}')
        if not self.pa_power.read():
            self.pa_power.write(gpio.LOW)
            print(f'Set value to {self.pa_power.read()}')

    def command_parser(self, command_obj, num_active_ptt):
        match command_obj.command:
            case ['l-band', 'rf-ptt', 'on']:
                num_active_ptt = self.rf_ptt_on(command_obj, num_active_ptt)
            case ['l-band', 'rf-ptt', 'off']:
                num_active_ptt = self.rf_ptt_off(command_obj, num_active_ptt)
            case ['l-band', 'rf-ptt', 'status']:
                self.component_status(command_obj)
            case ['l-band', 'pa-power', 'on']:
                if self.molly_guard(command_obj):
                    self.pa_power_on(command_obj)
            case ['l-band', 'pa-power', 'off']:
                self.pa_power_off(command_obj)
            case ['l-band', 'pa-power', 'status']:
                self.component_status(command_obj)
            case _:
                command_obj.invalid_command_response()

        return num_active_ptt


class Accessory:
    def __init__(self):
        self.name = None

        self.power = None

    def status(self, command_obj):
        status = {}
        # Power
        if self.power is not None:
            status.update({'power': 'ON'}) if self.power.read() is ON else status.update({'power': 'OFF'})
        else:
            status.update({'power': 'N/A'})

        message = 'Device: {}\n' \
                  'Power: {}\n\n' \
                  .format(self.name, status['power'])
        command_obj.send_response(message)

    def component_status(self, command_obj):
        component = command_obj.command[1]
        try:
            match component:
                case 'power':
                    if self.power.read() is None:
                        raise No_Component

                    message = 'ON\n' if self.power.read() is ON else 'OFF\n'
                    command_obj.send_response(message)
        except No_Component:
            message = f'FAIL: {component} No Component\n'
            command_obj.send_response(message)
        except Exception as error:
            print(error)

    def power_on(self, command_obj):
        try:
            if self.power.read() is ON:
                raise Redundant_Request

            self.power.write(gpio.HIGH)
            command_obj.success_response()
        except Redundant_Request:
            command_obj.no_change_response()
        except Exception as error:
            print(error)

    def power_off(self, command_obj):
        try:
            if self.power.read() is OFF:
                raise Redundant_Request

            self.power.write(gpio.LOW)
            command_obj.success_response()
        except Redundant_Request:
            command_obj.no_change_response()
        except Exception as error:
            print(error)


class RX_Swap(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'RX-Swap'
        # Power
        self.power = gpio.GPIOPin(RX_SWAP_POWER, None, initial=None)
        print(f'GPIOPin object returned with value: {self.power.read()}')
        if self.power.get_direction() != gpio.OUT:
            print('Direction is not out. Setting.')
            self.power.set_direction(gpio.OUT)
            print(f'value: {self.power.read()}')
        if not self.power.read():
            self.power.write(gpio.LOW)
            print(f'Set value to {self.power.read()}')

    def rx_swap_power_on(self, command_obj, num_active_ptt):
        try:
            if self.power.read() is ON:
                raise Redundant_Request
            # Fail if PTT is on
            if num_active_ptt > 0:
                raise PTT_Conflict

            self.power.write(gpio.LOW)
            command_obj.success_response()
        except Redundant_Request:
            command_obj.no_change_response()
        except PTT_Conflict:
            command_obj.ptt_conflict_response()
        except Exception as error:
            print(error)

    def rx_swap_power_off(self, command_obj, num_active_ptt):
        try:
            if self.power.read() is OFF:
                raise Redundant_Request
            # Fail if PTT is on
            if num_active_ptt > 0:
                raise PTT_Conflict

            self.power.write(gpio.LOW)
            command_obj.success_response()
        except Redundant_Request:
            command_obj.no_change_response()
        except PTT_Conflict:
            command_obj.ptt_conflict_response()
        except Exception as error:
            print(error)

    def command_parser(self, command_obj, num_active_ptt):
        match command_obj.command:
            case ['rx-swap', 'power', 'on']:
                self.rx_swap_power_on(command_obj, num_active_ptt)
            case ['rx-swap', 'power', 'off']:
                self.rx_swap_power_off(command_obj, num_active_ptt)
            case ['rx-swap', 'power', 'status']:
                self.component_status(command_obj)
            case ['rx-swap', 'status']:
                self.status(command_obj)
            case _:
                command_obj.invalid_command_response()


class SBC_Satnogs(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'SBC-Satnogs'
        # Power
        self.power = gpio.GPIOPin(SBC_SATNOGS_POWER, None, initial=None)
        print(f'GPIOPin object returned with value: {self.power.read()}')
        if self.power.get_direction() != gpio.OUT:
            print('Direction is not out. Setting.')
            self.power.set_direction(gpio.OUT)
            print(f'value: {self.power.read()}')
        if not self.power.read():
            self.power.write(gpio.LOW)
            print(f'Set value to {self.power.read()}')

    def command_parser(self, command_obj):
        match command_obj.command:
            case ['sbc-satnogs', 'power', 'on']:
                self.power_on(command_obj)
            case ['sbc-satnogs', 'power', 'off']:
                self.power_off(command_obj)
            case ['sbc-satnogs', 'power', 'status']:
                self.component_status(command_obj)
            case ['sbc-satnogs', 'status']:
                self.status(command_obj)
            case _:
                command_obj.invalid_command_response()


class SDR_Lime(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'SDR-Lime'
        # Power
        self.power = gpio.GPIOPin(SDR_LIME_POWER, None, initial=None)
        print(f'GPIOPin object returned with value: {self.power.read()}')
        if self.power.get_direction() != gpio.OUT:
            print('Direction is not out. Setting.')
            self.power.set_direction(gpio.OUT)
            print(f'value: {self.power.read()}')
        if not self.power.read():
            self.power.write(gpio.LOW)
            print(f'Set value to {self.power.read()}')

    def command_parser(self, command_obj):
        match command_obj.command:
            case ['sdr-lime', 'power', 'on']:
                self.power_on(command_obj)
            case ['sdr-lime', 'power', 'off']:
                self.power_off(command_obj)
            case ['sdr-lime', 'power', 'status']:
                self.component_status(command_obj)
            case ['sdr-lime', 'status']:
                self.status(command_obj)
            case _:
                command_obj.invalid_command_response()


class Rotator(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'Rotator'
        # Power
        self.power = gpio.GPIOPin(ROTATOR_POWER, None, initial=None)
        print(f'GPIOPin object returned with value: {self.power.read()}')
        if self.power.get_direction() != gpio.OUT:
            print('Direction is not out. Setting.')
            self.power.set_direction(gpio.OUT)
            print(f'value: {self.power.read()}')
        if not self.power.read():
            self.power.write(gpio.LOW)
            print(f'Set value to {self.power.read()}')

    def command_parser(self, command_obj):
        match command_obj.command:
            case ['rotator', 'power', 'on']:
                self.power_on(command_obj)
            case ['rotator', 'power', 'off']:
                self.power_off(command_obj)
            case ['rotator', 'power', 'status']:
                self.component_status(command_obj)
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

        message = f'SUCCESS: {device} {component} {state}\n'
        self.sock.sendto(message.encode('utf-8'), self.addr)

        logging.debug(f'{str(datetime.now())} {message.strip()}, ADDRESS: {str(self.addr)}')

    def no_change_response(self):
        device = self.command[0]
        component = self.command[1]
        state = self.command[2]

        message = f'WARNING: {device}  {component} {state} No Change\n'
        self.sock.sendto(message.encode('utf-8'), self.addr)

        logging.debug(f'{str(datetime.now())} {message.strip()}, ADDRESS: {str(self.addr)}')

    def ptt_conflict_response(self):
        device = self.command[0]
        component = self.command[1]
        state = self.command[2]

        message = f'FAIL: {device} {component} {state} PTT Conflict\n'
        self.sock.sendto(message.encode('utf-8'), self.addr)

        logging.debug(f'{str(datetime.now())} {message.strip()}, ADDRESS: {str(self.addr)}')

    def invalid_command_response(self):
        device = self.command[0]
        component = self.command[1]
        state = self.command[2]

        message = f'FAIL: {device} {component} {state} Invalid Command\n'
        self.sock.sendto(message.encode('utf-8'), self.addr)

        logging.debug(f'{str(datetime.now())} {message.strip()}, ADDRESS: {str(self.addr)}')

    def molly_guard_response(self):
        message = 'Re-enter the command within the next 20 seconds' \
                  ' if you would like to proceed\n'
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

        # Active PTT on initialization?
        self.num_active_ptt = 0

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
                    self.num_active_ptt = self.vhf.command_parser(command_obj, self.num_active_ptt)
                case 'uhf':
                    self.num_active_ptt = self.uhf.command_parser(command_obj, self.num_active_ptt)
                case 'l-band':
                    self.num_active_ptt = self.l_band.command_parser(command_obj, self.num_active_ptt)
                case 'rx-swap':
                    self.rx_swap.command_parser(command_obj, self.num_active_ptt)
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


class Max_PTT(Exception):
    pass


class Redundant_Request(Exception):
    pass


class No_Component(Exception):
    pass


def main():
    sd = StationD()
    sd.command_listener()


if __name__ == "__main__":
    print('===============================')
    print('Station Daemon Power Management')
    print('===============================')

    main()
