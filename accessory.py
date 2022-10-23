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

    def rx_swap_ptt_check(self, command_obj):
        if isinstance(self, RX_Swap) and command_obj.num_active_ptt > 0:
            raise sd.PTT_Conflict(command_obj)

    def power_on(self, command_obj):
        # RX-Swap cannot happen while any PTT is active
        self.rx_swap_ptt_check(command_obj)
        if self.power.read() is sd.ON:
            sd.no_change_response(command_obj)
            return
        self.power.write(sd.ON)
        sd.success_response(command_obj)

    def power_off(self, command_obj):
        # RX-Swap cannot happen while any PTT is active
        self.rx_swap_ptt_check(command_obj)
        if self.power.read() is sd.OFF:
            sd.no_change_response(command_obj)
            return
        self.power.write(sd.OFF)
        sd.success_response(command_obj)


class RX_Swap(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'RX-Swap'
        self.power = sd.assert_out(sd.gpio.GPIOPin(int(sd.config['RX-SWAP']['power_pin']), None, initial=None))


class SBC_Satnogs(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'SBC-Satnogs'
        self.power = sd.assert_out(sd.gpio.GPIOPin(int(sd.config['SBC-SATNOGS']['power_pin']), None, initial=None))


class SDR_Lime(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'SDR-Lime'
        self.power = sd.assert_out(sd.gpio.GPIOPin(int(sd.config['SDR-LIME']['power_pin']), None, initial=None))


class Rotator(Accessory):
    def __init__(self):
        super().__init__()
        self.name = 'Rotator'
        self.power = sd.assert_out(sd.gpio.GPIOPin(int(sd.config['ROTATOR']['power_pin']), None, initial=None))
