from . import stationd as sd
from .constants import OFF, ON


class Accessory:
    """Base class for station accessories with GPIO power control.

    This class provides common functionality for station accessories that can be
    controlled via GPIO pins. All accessories have power control capabilities
    and support status reporting via network commands (UDP).
    """

    def __init__(self, device_name: str) -> None:
        """Initialize a new Accessory instance.

        Sets up the base attributes for an accessory including the power GPIO
        pin.
        """
        self.device_name = device_name
        self.power_line = sd.assert_out(self.device_name, "power_pin")

        pin_info = sd.gpio_alloc.get_pin_info("power_pin")
        if pin_info:
            self.power_pin = pin_info[1]
        else:
            raise RuntimeError(f"Power pin not found for device {device_name}")

    def device_status(self, command: list[str]) -> str:
        return f'{command[0]} power {sd.get_state(self.power_line)}\n'

    def component_status(self, command: list[str]) -> str:
        try:
            component_name = command[1].replace('-', '_')
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
