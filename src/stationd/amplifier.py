import time

from . import stationd as sd
from .constants import OFF, ON

MOLLY_TIME = 20  # In seconds
PTT_COOLDOWN = 120  # In seconds
SLEEP_TIMER = 0.1

# Polarization directions
LEFT = ON
RIGHT = OFF


class MollyGuardError(Exception):
    """Exception raised when molly guard protection is triggered.

    Used to prevent accidental execution of potentially dangerous commands by
    requiring confirmation within a time window.
    """

    def __init__(self, seconds: float) -> None:
        """Initialize Molly Guard exception."""
        self.seconds = seconds


class PTTCooldownError(Exception):
    """Exception raised when PTT cooldown period is not satisfied.

    Enforces mandatory waiting period between PTT operations for hardware
    protection.
    """

    def __init__(self, seconds: float) -> None:
        """Initialize Push-to-Talk Cooldown exception."""
        self.seconds = seconds


class TxAmplifier:
    """Controls for a TX only amplifier.

    This class provides common functionality for controlling RF amplifiers
    That have a RF PTT (Push-To-Talk) switch and a power amplifier (PA).
    """

    def __init__(self, active_ptt: 'sd.ActivePTT', section: str) -> None:
        """Initialize a new Amplifier instance."""
        self.active_ptt = active_ptt
        self.section = section

        self.rf_ptt = sd.assert_out(f"{section}_rf_ptt", "rf_ptt_pin")
        self.pa_power = sd.assert_out(f"{section}_pa_power", "pa_power_pin")

        self.molly_guard_time = time.time() - MOLLY_TIME
        self.ptt_off_time = time.time() - PTT_COOLDOWN

    def device_status(self, command: list[str]) -> str:
        rf_ptt_state = sd.get_state(self.rf_ptt, self._get_pin_number("rf_ptt_pin"))
        pa_power_state = sd.get_state(self.pa_power, self._get_pin_number("pa_power_pin"))
        return f'{command[0]} rf-ptt {rf_ptt_state}\n{command[0]} pa-power {pa_power_state}\n'

    def component_status(self, command: list[str]) -> str:
        try:
            component_name = command[1].replace('-', '_')

            if component_name in ['rf_ptt', 'pa_power']:
                component = getattr(self, component_name)
                pin_info = sd.gpio_alloc.get_pin_info(f"{component_name}_pin")
                if pin_info:
                    return sd.get_status(component, pin_info[1], command)

            if hasattr(self, component_name):
                component = getattr(self, component_name)
                pin_info = sd.gpio_alloc.get_pin_info(f"{component_name}_pin")
                if pin_info:
                    return sd.get_status(component, pin_info[1], command)

            raise sd.InvalidCommandError
        except AttributeError as error:
            raise sd.InvalidCommandError from error

    def check_molly_guard(self) -> None:
        if time.time() - self.molly_guard_time > MOLLY_TIME:
            self.molly_guard_time = time.time()
            raise MollyGuardError(MOLLY_TIME)

    def rf_ptt_on(self) -> None:
        if sd.get_state(self.rf_ptt, self._get_pin_number("rf_ptt_pin")) == "ON":
            raise sd.NoChangeError
        if sd.get_state(self.pa_power, self._get_pin_number("pa_power_pin")) == "OFF":
            raise sd.PTTConflictError

        # brief cooldown
        time.sleep(SLEEP_TIMER)
        self.active_ptt.inc()

        sd.power_on(self.rf_ptt, self._get_pin_number("rf_ptt_pin"))

    def rf_ptt_off(self) -> None:
        if sd.get_state(self.rf_ptt, self._get_pin_number("rf_ptt_pin")) == "OFF":
            raise sd.NoChangeError

        sd.power_off(self.rf_ptt, self._get_pin_number("rf_ptt_pin"))

        #  set time ptt turned off
        self.ptt_off_time = time.time()
        self.active_ptt.dec()

    def pa_power_on(self) -> None:
        if sd.get_state(self.pa_power, self._get_pin_number("pa_power_pin")) == "ON":
            raise sd.NoChangeError
        self.check_molly_guard()

        sd.power_on(self.pa_power, self._get_pin_number("pa_power_pin"))

    def pa_power_off(self) -> None:
        if sd.get_state(self.pa_power, self._get_pin_number("pa_power_pin")) == "OFF":
            raise sd.NoChangeError
        if sd.get_state(self.rf_ptt, self._get_pin_number("rf_ptt_pin")) == "ON":
            raise sd.PTTConflictError
        #  Check PTT off for at least 2 minutes
        diff_sec = time.time() - self.ptt_off_time
        if diff_sec <= PTT_COOLDOWN:
            raise PTTCooldownError(round(PTT_COOLDOWN - diff_sec))

        sd.power_off(self.pa_power, self._get_pin_number("pa_power_pin"))

    def _get_pin_number(self, pin_name: str) -> int:
        """Get the pin number for a given pin name from GPIO allocator."""
        pin_info = sd.gpio_alloc.get_pin_info(pin_name)
        if pin_info:
            return pin_info[1]
        raise RuntimeError(f"Pin {pin_name} not found")


class RxTxAmplifier(TxAmplifier):
    """Controls for a channel with both TX and RX amplifiers.

    This class provides common functionality for controlling RF amplifiers
    including transmit/receive relay control, RF PTT (Push-To-Talk), power
    amplifier control, LNA (Low Noise Amplifier) control, and antenna
    polarization switching.
    """

    def __init__(self, active_ptt: 'sd.ActivePTT', section: str) -> None:
        """Initialize a new Amplifier instance."""
        super().__init__(active_ptt, section)

        self.tr_relay = sd.assert_out(f"{section}_tr_relay", "tr_relay_pin")
        self.lna = sd.assert_out(f"{section}_lna", "lna_pin")
        self.polarization = sd.assert_out(f"{section}_polarization", "polarization_pin")

    def device_status(self, command: list[str]) -> str:
        polarization_state = sd.get_state(
            self.polarization, self._get_pin_number("polarization_pin")
        )
        p_state = "LEFT" if polarization_state == "ON" else "RIGHT"
        tr_relay_state = sd.get_state(self.tr_relay, self._get_pin_number("tr_relay_pin"))
        lna_state = sd.get_state(self.lna, self._get_pin_number("lna_pin"))

        return super().device_status(command) + (
            f'{command[0]} tr-relay {tr_relay_state}\n'
            f'{command[0]} lna {lna_state}\n'
            f'{command[0]} polarization {p_state}\n'
        )

    def component_status(self, command: list[str]) -> str:
        if command[1] == "polarization":
            polarization_state = sd.get_state(
                self.polarization, self._get_pin_number("polarization_pin")
            )
            p_state = "LEFT" if polarization_state == "ON" else "RIGHT"
            return f'{command[0]} {command[1]} {p_state}\n'

        return super().component_status(command)

    def rf_ptt_on(self) -> None:
        super().rf_ptt_on()
        # Enforce tr-relay and ptt are same state
        self.tr_relay_on()
        # Ptt command received, turn off LNA
        if sd.get_state(self.lna, self._get_pin_number("lna_pin")) != "OFF":
            sd.power_off(self.lna, self._get_pin_number("lna_pin"))

    def rf_ptt_off(self) -> None:
        super().rf_ptt_off()
        # Enforce tr-relay and ptt are same state
        self.tr_relay_off()

    def pa_power_on(self) -> None:
        super().pa_power_on()
        self.tr_relay_on()

    def pa_power_off(self) -> None:
        super().pa_power_off()
        self.tr_relay_off()

    def tr_relay_on(self) -> None:
        if sd.get_state(self.tr_relay, self._get_pin_number("tr_relay_pin")) == "ON":
            return
        sd.power_on(self.tr_relay, self._get_pin_number("tr_relay_pin"))

    def tr_relay_off(self) -> None:
        if sd.get_state(self.tr_relay, self._get_pin_number("tr_relay_pin")) == "OFF":
            return
        sd.power_off(self.tr_relay, self._get_pin_number("tr_relay_pin"))

    def lna_on(self) -> None:
        if sd.get_state(self.lna, self._get_pin_number("lna_pin")) == "ON":
            raise sd.NoChangeError
        #  Fail if PTT is on
        if sd.get_state(self.rf_ptt, self._get_pin_number("rf_ptt_pin")) == "ON":
            raise sd.PTTConflictError
        sd.power_on(self.lna, self._get_pin_number("lna_pin"))

    def lna_off(self) -> None:
        if sd.get_state(self.lna, self._get_pin_number("lna_pin")) == "OFF":
            raise sd.NoChangeError
        sd.power_off(self.lna, self._get_pin_number("lna_pin"))

    def polarization_left(self) -> None:
        if sd.get_state(self.polarization, self._get_pin_number("polarization_pin")) == "ON":
            raise sd.NoChangeError
        if sd.get_state(self.rf_ptt, self._get_pin_number("rf_ptt_pin")) == "ON":
            raise sd.PTTConflictError
        # brief cooldown
        time.sleep(SLEEP_TIMER)
        sd.power_on(self.polarization, self._get_pin_number("polarization_pin"))

    def polarization_right(self) -> None:
        if sd.get_state(self.polarization, self._get_pin_number("polarization_pin")) == "OFF":
            raise sd.NoChangeError
        if sd.get_state(self.rf_ptt, self._get_pin_number("rf_ptt_pin")) == "ON":
            raise sd.PTTConflictError
        # brief cooldown
        time.sleep(SLEEP_TIMER)
        sd.power_off(self.polarization, self._get_pin_number("polarization_pin"))


class VHF(RxTxAmplifier):
    """VHF amplifier control.

    Controls VHF band RF amplifier including transmit/receive relay, RF PTT,
    power amplifier, LNA, and polarization switching. Configured for VHF
    frequency band operation.
    """

    def __init__(self, active_ptt: 'sd.ActivePTT') -> None:
        """Initialize the VHF amplifier.

        Sets up the VHF amplifier with all its GPIO control pins.
        """
        super().__init__(active_ptt, 'VHF')


class UHF(RxTxAmplifier):
    """UHF amplifier control.

    Controls UHF band RF amplifier including transmit/receive relay, RF PTT,
    power amplifier, LNA, and polarization switching. Configured for UHF
    frequency band operation.
    """

    def __init__(self, active_ptt: 'sd.ActivePTT') -> None:
        """Initialize the UHF amplifier.

        Sets up the UHF amplifier with all its GPIO control pins.
        """
        super().__init__(active_ptt, 'UHF')


class LBand(TxAmplifier):
    """L-Band frequency amplifier control.

    Controls L-Band RF amplifier with RF PTT and power amplifier control.
    This amplifier is configured for L-Band frequency operation and has a
    simplified control interface without transmit/receive relay, LNA, or
    polarization switching.
    """

    def __init__(self, active_ptt: 'sd.ActivePTT') -> None:
        """Initialize the L-Band amplifier.

        Sets up the L-Band amplifier with RF PTT and power amplifier GPIO
        control pins.

        Note: L-Band amplifier does not include TR relay, LNA, or polarization
              controls.
        """
        super().__init__(active_ptt, 'L-BAND')
