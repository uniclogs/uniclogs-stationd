from . import stationd as sd
from .gpio.gpio import GPIOPin


class Accessory:
    """Base class for station accessories with GPIO power control.

    This class provides common functionality for station accessories that can be
    controlled via GPIO pins. All accessories have power control capabilities
    and support status reporting via network commands (UDP).
    """

    def __init__(self, config_section: str) -> None:
        """Initialize a new Accessory instance.

        Sets up the base attributes for an accessory including the power GPIO
        pin.
        """
        self.power = sd.assert_out(
            GPIOPin(int(sd.config[config_section]['power_pin']), None, initial=None)
        )

    def device_status(self, command_obj: 'sd.Command') -> None:
        status = f'{command_obj.command[0]} power {sd.get_state(self.power)}\n'
        sd.status_response(command_obj, status)

    def component_status(self, command_obj: 'sd.Command') -> None:
        try:
            component = getattr(self, command_obj.command[1].replace('-', '_'))
        except AttributeError as error:
            raise sd.InvalidCommandError(command_obj) from error

        status = sd.get_status(component, command_obj)
        sd.status_response(command_obj, status)

    def power_on(self, command_obj: 'sd.Command') -> None:
        if self.power.read() == sd.ON:
            raise sd.NoChangeError
        self.power.write(sd.ON)
        sd.success_response(command_obj)

    def power_off(self, command_obj: 'sd.Command') -> None:
        if self.power.read() == sd.OFF:
            raise sd.NoChangeError
        self.power.write(sd.OFF)
        sd.success_response(command_obj)


class VUTxRelay(Accessory):
    """VHF/UHF transmit relay control.

    Controls the VU TX relay which switches between VHF and UHF transmission
    paths.
    """

    def __init__(self) -> None:
        """Initialize the VHF/UHF TX Relay accessory.

        Sets up the VU TX relay with its configured GPIO power pin.
        """
        super().__init__('VU-TX-RELAY')

    def _ptt_check(self, command_obj: 'sd.Command') -> None:
        # VU TX Relay change cannot happen while any PTT is active
        if command_obj.num_active_ptt > 0:
            raise sd.PTTConflictError(command_obj)

    def power_on(self, command_obj: 'sd.Command') -> None:
        self._ptt_check(command_obj)
        super().power_on(command_obj)

    def power_off(self, command_obj: 'sd.Command') -> None:
        self._ptt_check(command_obj)
        super().power_off(command_obj)


class SatnogsHost(Accessory):
    """SatNOGS host power control.

    Controls power to the SatNOGS host which handles satellite tracking
    and observation scheduling.
    """

    def __init__(self) -> None:
        """Initialize the SatNOGS Host accessory.

        Sets up the SatNOGS host power control with its configured GPIO power
        pin.
        """
        super().__init__('SATNOGS-HOST')


class RadioHost(Accessory):
    """Radio host power control.

    Controls power to the radio host which manages radio communication and
    digital signal processing.
    """

    def __init__(self) -> None:
        """Initialize the Radio Host accessory.

        Sets up the radio host power control with its configured GPIO power pin.
        """
        super().__init__('RADIO-HOST')


class Rotator(Accessory):
    """Antenna rotator power control.

    Controls power to the antenna rotator system which provides azimuth and
    elevation positioning for directional antennas during satellite passes.
    """

    def __init__(self) -> None:
        """Initialize the Rotator accessory.

        Sets up the antenna rotator power control with its configured GPIO power
        pin.
        """
        super().__init__('ROTATOR')


class SDRB200(Accessory):
    """USRP B200 SDR power control.

    Controls power to the USRP B200 Software Defined Radio which provides
    RF reception and transmission capabilities for the ground station.
    """

    def __init__(self) -> None:
        """Initialize the SDR B200 accessory.

        Sets up the USRP B200 SDR power control with its configured
        GPIO power pin.
        """
        super().__init__('SDR-B200')
