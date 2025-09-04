from . import stationd as sd
from .constants import OFF, ON


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
        self.config_section = config_section
        self.power_pin = int(sd.config[config_section]["power_pin"])
        self.power_line = sd.assert_out(self.power_pin, config_section)

    def device_status(self, command: list[str]) -> str:
        return f'{command[0]} power {sd.get_state(self.power_line)}\n'

    def component_status(self, command: list[str]) -> str:
        try:
            component_name = command[1].replace('-', '_')
            # For accessories, the main component is the power line
            if component_name == 'power':
                return sd.get_status(self.power_line, self.power_pin, command)
            else:
                component = getattr(self, component_name)
                if hasattr(component, 'power_line') and hasattr(component, 'power_pin'):
                    return sd.get_status(component.power_line, component.power_pin, command)
                else:
                    raise sd.InvalidCommandError
        except AttributeError as error:
            raise sd.InvalidCommandError from error

    def power_on(self) -> None:
        """Turn on the accessory."""
        if sd.get_state(self.power_line) == "ON":
            raise sd.NoChangeError
        sd.power_on(self.power_line, self.power_pin)

    def power_off(self) -> None:
        """Turn off the accessory."""
        if sd.get_state(self.power_line) == "OFF":
            raise sd.NoChangeError
        sd.power_off(self.power_line, self.power_pin)


class VUTxRelay(Accessory):
    """VHF/UHF transmit relay control.

    Controls the VU TX relay which switches between VHF and UHF transmission
    paths.
    """

    def __init__(self, active_ptt: 'sd.ActivePTT') -> None:
        """Initialize the VHF/UHF TX Relay accessory.

        Sets up the VU TX relay with its configured GPIO power pin.
        """
        super().__init__('VU-TX-RELAY')
        self.active_ptt = active_ptt

    def _ptt_check(self) -> None:
        # VU TX Relay change cannot happen while any PTT is active
        if self.active_ptt.count > 0:
            raise sd.PTTConflictError

    def power_on(self) -> None:
        self._ptt_check()
        super().power_on()

    def power_off(self) -> None:
        self._ptt_check()
        super().power_off()


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
