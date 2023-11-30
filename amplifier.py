from multiprocessing import Manager
from datetime import datetime
from gpio import gpio
import time
import stationd as sd


class Amplifier:
    def __init__(self):
        self.name = None
        self.tr_relay = None
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
        status = f'{command_obj.command[0]} tr-relay {sd.get_state(self.tr_relay)}\n' \
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

    def tr_relay_on(self, command_obj):
        if self.tr_relay.read() is sd.ON:
            return
        self.tr_relay.write(sd.ON)

    def tr_relay_off(self, command_obj):
        if self.tr_relay.read() is sd.OFF:
            return
        self.tr_relay.write(sd.OFF)

    def rf_ptt_on(self, command_obj):
        if self.rf_ptt.read() is sd.ON:
            sd.no_change_response(command_obj)
            return
        if self.pa_power.read() is sd.OFF:
            raise sd.PTT_Conflict(command_obj)
        if command_obj.num_active_ptt >= sd.PTT_MAX_COUNT:
            raise sd.Max_PTT(command_obj)
        # Enforce tr-relay and ptt are same state
        if self.tr_relay is not None:
            self.tr_relay_on(command_obj)

        # Ptt command received, turn off LNA
        if self.lna is not None:
            self.lna_off(command_obj)
        # brief cooldown
        time.sleep(sd.SLEEP_TIMER)
        self.rf_ptt.write(sd.ON)
        sd.success_response(command_obj)
        command_obj.num_active_ptt += 1

    def rf_ptt_off(self, command_obj):
        if self.rf_ptt.read() is sd.OFF:
            sd.no_change_response(command_obj)
            return
        self.rf_ptt.write(sd.OFF)
        sd.success_response(command_obj)
        #  set time ptt turned off
        self.shared['ptt_off_time'] = datetime.now()
        command_obj.num_active_ptt -= 1
        # make sure num_active_ptt never falls below 0
        if command_obj.num_active_ptt < 0:
            command_obj.num_active_ptt = 0
        # Enforce tr-relay and ptt are same state
        if self.tr_relay is not None:
            self.tr_relay_off(command_obj)

    def pa_power_on(self, command_obj):
        if self.pa_power.read() is sd.ON:
            sd.no_change_response(command_obj)
            return
        if self.molly_guard(command_obj):
            if self.tr_relay is not None:
                self.tr_relay_on(command_obj)
            self.pa_power.write(sd.ON)
            sd.success_response(command_obj)

    def pa_power_off(self, command_obj):
        if self.pa_power.read() is sd.OFF:
            sd.no_change_response(command_obj)
            return
        if self.rf_ptt.read() is sd.ON:
            raise sd.PTT_Conflict(command_obj)
        #  Check PTT off for at least 2 minutes
        diff_sec = sd.calculate_diff_sec(self.shared['ptt_off_time'])
        if diff_sec > sd.PTT_COOLDOWN:
            if self.tr_relay is not None:
                self.tr_relay_off(command_obj)
            self.pa_power.write(sd.OFF)
            sd.success_response(command_obj)
        else:
            raise sd.PTT_Cooldown(round(sd.PTT_COOLDOWN - diff_sec))

    def lna_on(self, command_obj):
        if self.lna.read() is sd.ON:
            sd.no_change_response(command_obj)
            return
        #  Fail if PTT is on
        if self.rf_ptt.read() is sd.ON:
            raise sd.PTT_Conflict(command_obj)
        self.lna.write(sd.ON)
        sd.success_response(command_obj)

    def lna_off(self, command_obj):
        if self.lna.read() is sd.OFF:
            # only send response if called directly via command
            if command_obj.command[1] == 'lna':
                sd.no_change_response(command_obj)
                return
        self.lna.write(sd.OFF)
        # only send response if called directly via command
        if command_obj.command[1] == 'lna':
            sd.success_response(command_obj)

    def polarization_left(self, command_obj):
        if self.polarization.read() is sd.LEFT:
            sd.no_change_response(command_obj)
            return
        if self.rf_ptt.read() is sd.ON:
            raise sd.PTT_Conflict(command_obj)
        # brief cooldown
        time.sleep(sd.SLEEP_TIMER)
        self.polarization.write(sd.LEFT)
        sd.success_response(command_obj)

    def polarization_right(self, command_obj):
        if self.polarization.read() is sd.RIGHT:
            sd.no_change_response(command_obj)
            return
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
        self.tr_relay = sd.assert_out(gpio.GPIOPin(int(sd.config['VHF']['tr_relay_pin']), None, initial=None))
        self.rf_ptt = sd.assert_out(gpio.GPIOPin(int(sd.config['VHF']['rf_ptt_pin']), None, initial=None))
        self.pa_power = sd.assert_out(gpio.GPIOPin(int(sd.config['VHF']['pa_power_pin']), None, initial=None))
        self.lna = sd.assert_out(gpio.GPIOPin(int(sd.config['VHF']['lna_pin']), None, initial=None))
        self.polarization = sd.assert_out(gpio.GPIOPin(int(sd.config['VHF']['polarization_pin']), None, initial=None))


class UHF(Amplifier):
    def __init__(self):
        super().__init__()
        self.name = 'UHF'
        self.tr_relay = sd.assert_out(gpio.GPIOPin(int(sd.config['UHF']['tr_relay_pin']), None, initial=None))
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
