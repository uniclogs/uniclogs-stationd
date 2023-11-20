import stationd as sd


class Accessory:
    def __init__(self):
        self.name = None
        self.power = None

    def device_status(self, command_obj):
        status = f'{command_obj.command[0]} power {sd.get_state(self.power)}\n'
        sd.status_response(command_obj, status)

    def component_status(self, command_obj):
        try:
            component = getattr(self, command_obj.command[1].replace('-', '_'))
            status = sd.get_status(component, command_obj)
            sd.status_response(command_obj, status)
        except AttributeError:
            raise sd.Invalid_Command(command_obj)

    def vu_tx_relay_ptt_check(self, command_obj):
        if isinstance(self, VU_TX_Relay) and command_obj.num_active_ptt > 0:
            raise sd.PTT_Conflict(command_obj)

    def power_on(self, command_obj):
        # VU TX Relay change cannot happen while any PTT is active
        self.vu_tx_relay_ptt_check(command_obj)
        if self.power.read() is sd.ON:
            sd.no_change_response(command_obj)
            return
        self.power.write(sd.ON)
        sd.success_response(command_obj)

    def power_off(self, command_obj):
        # VU TX Relay change cannot happen while any PTT is active
        self.vu_tx_relay_ptt_check(command_obj)
        if self.power.read() is sd.OFF:
            sd.no_change_response(command_obj)
            return
        self.power.write(sd.OFF)
        sd.success_response(command_obj)


class VU_TX_Relay(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'VU-TX-Relay'
        self.power = sd.assert_out(sd.gpio.GPIOPin(int(sd.config['VU-TX-RELAY']['power_pin']), None, initial=None))


class Satnogs_Host(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'Satnogs-Host'
        self.power = sd.assert_out(sd.gpio.GPIOPin(int(sd.config['SATNOGS-HOST']['power_pin']), None, initial=None))


class Radio_Host(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'Radio-Host'
        self.power = sd.assert_out(sd.gpio.GPIOPin(int(sd.config['RADIO-HOST']['power_pin']), None, initial=None))


class Rotator(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'Rotator'
        self.power = sd.assert_out(sd.gpio.GPIOPin(int(sd.config['ROTATOR']['power_pin']), None, initial=None))
