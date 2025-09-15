import gpiod

from . import stationd as sd


class Accessory:
    """Base class for station accessories with GPIO power control.

    This class provides common functionality for station accessories that can be
    controlled via GPIO pins. All accessories have power control capabilities
    and support status reporting via network commands (UDP).
    """

    def __init__(self, config_section: str) -> None:
        """Initialize a new Accessory instance.

        Sets up the base attributes for an accessory.
        """
        gpio_chip, gpio_pin = sd.config[config_section]['power_pin'].split(' ')
        self._power = sd.LineOut(f"/dev/gpiochip{gpio_chip}", int(gpio_pin))
        self._power.value = gpiod.line.Value.ACTIVE

    def device_status(self, command: list[str]) -> str:
        """Get the power status of an accessory device."""
        return self.component_status([command[0], 'power', *command[1:]])

    def component_status(self, command: list[str]) -> str:
        """Get the power status of an accessory device component."""
        if command[1] != 'power':
            raise sd.InvalidCommandError

        state = 'ON' if self._power.value == gpiod.line.Value.ACTIVE else 'OFF'
        return f'{command[0]} {command[1]} {state}\n'

    def power_on(self) -> None:
        """Turn on the accessory."""
        if self._power.value == gpiod.line.Value.ACTIVE:
            raise sd.NoChangeError
        self._power.value = gpiod.line.Value.ACTIVE

    def power_off(self) -> None:
        """Turn off the accessory."""
        if self._power.value == gpiod.line.Value.INACTIVE:
            raise sd.NoChangeError
        self._power.value = gpiod.line.Value.INACTIVE


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
