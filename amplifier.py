from multiprocessing import Manager
from datetime import datetime
from gpio import gpio
import time
import stationd as sd


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

    def device_status(self, command_obj):
        p_state = 'LEFT' if sd.get_state(self.polarization) is sd.LEFT else 'RIGHT'
        status = f'{command_obj.command[0]} dow-key {sd.get_state(self.dow_key)}\n' \
                 f'{command_obj.command[0]} rf-ptt {sd.get_state(self.rf_ptt)}\n' \
                 f'{command_obj.command[0]} pa-power {sd.get_state(self.pa_power)}\n' \
                 f'{command_obj.command[0]} lna {sd.get_state(self.lna)}\n' \
                 f'{command_obj.command[0]} polarization {p_state}\n'
        sd.status_response(command_obj, status)

    def component_status(self, command_obj):
        try:
            component = getattr(self, command_obj.command[1].replace('-', '_'))
            if command_obj.command[1] == 'polarization':
                p_state = 'LEFT' if sd.get_state(self.polarization) is sd.LEFT else 'RIGHT'
                status = f'{command_obj.command[0]} {command_obj.command[1]} {p_state}\n'
                sd.status_response(command_obj, status)
            else:
                status = sd.get_status(component, command_obj)
                sd.status_response(command_obj, status)
        except AttributeError:
            raise sd.Invalid_Command(command_obj)

    def molly_guard(self, command_obj):
        diff_sec = sd.calculate_diff_sec(self.molly_guard_time)
        if diff_sec is None or diff_sec > 20:
            self.molly_guard_time = datetime.now()
            raise sd.Molly_Guard(command_obj)
        else:
            # reset timer to none
            self.molly_guard_time = None
            return True

    def dow_key_on(self, command_obj):
        if self.dow_key.read() is sd.ON:
            raise sd.No_Change(command_obj)
        self.dow_key.write(sd.ON)

    def dow_key_off(self, command_obj):
        if self.dow_key.read() is sd.OFF:
            raise sd.No_Change(command_obj)
        self.dow_key.write(sd.OFF)

    def rf_ptt_on(self, command_obj):
        if self.rf_ptt.read() is sd.ON:
            raise sd.No_Change(command_obj)
        if self.pa_power.read() is sd.OFF:
            raise sd.PTT_Conflict(command_obj)
        if command_obj.num_active_ptt >= sd.PTT_MAX_COUNT:
            raise sd.Max_PTT(command_obj)
        # Enforce dow-key and ptt are same state
        if self.dow_key is not None:
            try:
                self.dow_key_on(command_obj)
            except sd.No_Change:
                pass
        # Ptt command received, turn off LNA
        if self.lna is not None:
            try:
                self.lna_off(command_obj)
            except sd.No_Change:
                pass
        # brief cooldown
        time.sleep(sd.SLEEP_TIMER)
        self.rf_ptt.write(sd.ON)
        sd.success_response(command_obj)
        command_obj.num_active_ptt += 1

    def rf_ptt_off(self, command_obj):
        if self.rf_ptt.read() is sd.OFF:
            raise sd.No_Change(command_obj)
        self.rf_ptt.write(sd.OFF)
        sd.success_response(command_obj)
        #  set time ptt turned off
        self.shared['ptt_off_time'] = datetime.now()
        command_obj.num_active_ptt -= 1
        # make sure num_active_ptt never falls below 0
        if command_obj.num_active_ptt < 0:
            command_obj.num_active_ptt = 0
        # Enforce dow-key and ptt are same state
        if self.dow_key is not None:
            try:
                self.dow_key_off(command_obj)
            except sd.No_Change:
                pass

    def pa_power_on(self, command_obj):
        if self.pa_power.read() is sd.ON:
            raise sd.No_Change(command_obj)
        if self.molly_guard(command_obj):
            if self.dow_key is not None:
                try:
                    self.dow_key_on(command_obj)
                except sd.No_Change:
                    pass
            self.pa_power.write(sd.ON)
            sd.success_response(command_obj)

    def pa_power_off(self, command_obj):
        if self.pa_power.read() is sd.OFF:
            raise sd.No_Change(command_obj)
        if self.rf_ptt.read() is sd.ON:
            raise sd.PTT_Conflict(command_obj)
        #  Check PTT off for at least 2 minutes
        diff_sec = sd.calculate_diff_sec(self.shared['ptt_off_time'])
        if diff_sec > sd.PTT_COOLDOWN:
            if self.dow_key is not None:
                try:
                    self.dow_key_off(command_obj)
                except sd.No_Change:
                    pass
            self.pa_power.write(sd.OFF)
            sd.success_response(command_obj)
        else:
            raise sd.PTT_Cooldown(command_obj, round(sd.PTT_COOLDOWN - diff_sec))

    def lna_on(self, command_obj):
        if self.lna.read() is sd.ON:
            raise sd.No_Change(command_obj)
        #  Fail if PTT is on
        if self.rf_ptt.read() is sd.ON:
            raise sd.PTT_Conflict(command_obj)
        self.lna.write(sd.ON)
        sd.success_response(command_obj)

    def lna_off(self, command_obj):
        if self.lna.read() is sd.OFF:
            raise sd.No_Change(command_obj)
        self.lna.write(sd.OFF)
        # only send response if called directly via command
        if command_obj.command[1] == 'lna':
            sd.success_response(command_obj)

    def polarization_left(self, command_obj):
        if self.polarization.read() is sd.LEFT:
            raise sd.No_Change(command_obj)
        if self.rf_ptt.read() is sd.ON:
            raise sd.PTT_Conflict(command_obj)
        # brief cooldown
        time.sleep(sd.SLEEP_TIMER)
        self.polarization.write(sd.LEFT)
        sd.success_response(command_obj)

    def polarization_right(self, command_obj):
        if self.polarization.read() is sd.RIGHT:
            raise sd.No_Change(command_obj)
        if self.rf_ptt.read() is sd.ON:
            raise sd.PTT_Conflict(command_obj)
        # brief cooldown
        time.sleep(sd.SLEEP_TIMER)
        self.polarization.write(sd.RIGHT)
        sd.success_response(command_obj)


class VHF(Amplifier):
    def __init__(self):
        super().__init__()
        self.name = 'VHF'
        self.dow_key = sd.assert_out(gpio.GPIOPin(int(sd.config['VHF']['dow_key_pin']), None, initial=None))
        self.rf_ptt = sd.assert_out(gpio.GPIOPin(int(sd.config['VHF']['rf_ptt_pin']), None, initial=None))
        self.pa_power = sd.assert_out(gpio.GPIOPin(int(sd.config['VHF']['pa_power_pin']), None, initial=None))
        self.lna = sd.assert_out(gpio.GPIOPin(int(sd.config['VHF']['lna_pin']), None, initial=None))
        self.polarization = sd.assert_out(gpio.GPIOPin(int(sd.config['VHF']['polarization_pin']), None, initial=None))


class UHF(Amplifier):
    def __init__(self):
        super().__init__()
        self.name = 'UHF'
        self.dow_key = sd.assert_out(gpio.GPIOPin(int(sd.config['UHF']['dow_key_pin']), None, initial=None))
        self.rf_ptt = sd.assert_out(gpio.GPIOPin(int(sd.config['UHF']['rf_ptt_pin']), None, initial=None))
        self.pa_power = sd.assert_out(gpio.GPIOPin(int(sd.config['UHF']['pa_power_pin']), None, initial=None))
        self.lna = sd.assert_out(gpio.GPIOPin(int(sd.config['UHF']['lna_pin']), None, initial=None))
        self.polarization = sd.assert_out(gpio.GPIOPin(int(sd.config['UHF']['polarization_pin']), None, initial=None))


class L_Band(Amplifier):
    def __init__(self):
        super().__init__()
        self.name = 'L-Band'
        self.rf_ptt = sd.assert_out(gpio.GPIOPin(int(sd.config['L-BAND']['rf_ptt_pin']), None, initial=None))
        self.pa_power = sd.assert_out(gpio.GPIOPin(int(sd.config['L-BAND']['pa_power_pin']), None, initial=None))
