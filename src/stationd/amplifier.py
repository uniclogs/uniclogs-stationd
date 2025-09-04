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
        
        self.rf_ptt_pin = int(sd.config[section]['rf_ptt_pin'])
        self.rf_ptt = sd.assert_out(self.rf_ptt_pin, section)
        self.pa_power_pin = int(sd.config[section]['pa_power_pin'])
        self.pa_power = sd.assert_out(self.pa_power_pin, section)

        self.molly_guard_time = time.time() - MOLLY_TIME
        self.ptt_off_time = time.time() - PTT_COOLDOWN

    def device_status(self, command: list[str]) -> str:
        return (
            f'{command[0]} rf-ptt {sd.get_state(self.rf_ptt)}\n'
            f'{command[0]} pa-power {sd.get_state(self.pa_power)}\n'
        )

    def component_status(self, command: list[str]) -> str:
        try:
            component_name = command[1].replace('-', '_')
            if component_name == 'rf_ptt':
                return sd.get_status(self.rf_ptt, self.rf_ptt_pin, command)
            elif component_name == 'pa_power':
                return sd.get_status(self.pa_power, self.pa_power_pin, command)
            elif hasattr(self, component_name) and hasattr(self, f'{component_name}_pin'):
                # Generic handling for other GPIO components
                component = getattr(self, component_name)
                pin = getattr(self, f'{component_name}_pin')
                return sd.get_status(component, pin, command)
            else:
                raise sd.InvalidCommandError
        except AttributeError as error:
            raise sd.InvalidCommandError from error

    def check_molly_guard(self) -> None:
        if time.time() - self.molly_guard_time > MOLLY_TIME:
            self.molly_guard_time = time.time()
            raise MollyGuardError(MOLLY_TIME)

    def rf_ptt_on(self) -> None:
        if sd.get_state(self.rf_ptt) == "ON":
            raise sd.NoChangeError
        if sd.get_state(self.pa_power) == "OFF":
            raise sd.PTTConflictError

        # brief cooldown
        time.sleep(SLEEP_TIMER)
        self.active_ptt.inc()
        sd.power_on(self.rf_ptt, self.rf_ptt_pin)

    def rf_ptt_off(self) -> None:
        if sd.get_state(self.rf_ptt) == "OFF":
            raise sd.NoChangeError
        sd.power_off(self.rf_ptt, self.rf_ptt_pin)
        #  set time ptt turned off
        self.ptt_off_time = time.time()
        self.active_ptt.dec()

    def pa_power_on(self) -> None:
        if sd.get_state(self.pa_power) == "ON":
            raise sd.NoChangeError
        self.check_molly_guard()
        sd.power_on(self.pa_power, self.pa_power_pin)

    def pa_power_off(self) -> None:
        if sd.get_state(self.pa_power) == "OFF":
            raise sd.NoChangeError
        if sd.get_state(self.rf_ptt) == "ON":
            raise sd.PTTConflictError
        #  Check PTT off for at least 2 minutes
        diff_sec = time.time() - self.ptt_off_time
        if diff_sec <= PTT_COOLDOWN:
            raise PTTCooldownError(round(PTT_COOLDOWN - diff_sec))
        sd.power_off(self.pa_power, self.pa_power_pin)


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
        
        self.tr_relay_pin = int(sd.config[section]['tr_relay_pin'])
        self.tr_relay = sd.assert_out(self.tr_relay_pin, section)
        self.lna_pin = int(sd.config[section]['lna_pin'])
        self.lna = sd.assert_out(self.lna_pin, section)
        self.polarization_pin = int(sd.config[section]['polarization_pin'])
        self.polarization = sd.assert_out(self.polarization_pin, section)

    def device_status(self, command: list[str]) -> str:
        p_state = 'LEFT' if sd.get_state(self.polarization) == "ON" else 'RIGHT'
        return super().device_status(command) + (
            f'{command[0]} tr-relay {sd.get_state(self.tr_relay)}\n'
            f'{command[0]} lna {sd.get_state(self.lna)}\n'
            f'{command[0]} polarization {p_state}\n'
        )

    def component_status(self, command: list[str]) -> str:
        if command[1] == 'polarization':
            p_state = 'LEFT' if sd.get_state(self.polarization) == "ON" else 'RIGHT'
            return f'{command[0]} {command[1]} {p_state}\n'
        return super().component_status(command)

    def rf_ptt_on(self) -> None:
        super().rf_ptt_on()
        # Enforce tr-relay and ptt are same state
        self.tr_relay_on()
        # Ptt command received, turn off LNA
        if sd.get_state(self.lna) != "OFF":
            sd.power_off(self.lna, self.lna_pin)

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
        if sd.get_state(self.tr_relay) == "ON":
            return
        sd.power_on(self.tr_relay, self.tr_relay_pin)

    def tr_relay_off(self) -> None:
        if sd.get_state(self.tr_relay) == "OFF":
            return
        sd.power_off(self.tr_relay, self.tr_relay_pin)

    def lna_on(self) -> None:
        if sd.get_state(self.lna) == "ON":
            raise sd.NoChangeError
        #  Fail if PTT is on
        if sd.get_state(self.rf_ptt) == "ON":
            raise sd.PTTConflictError
        sd.power_on(self.lna, self.lna_pin)

    def lna_off(self) -> None:
        if sd.get_state(self.lna) == "OFF":
            raise sd.NoChangeError
        sd.power_off(self.lna, self.lna_pin)

    def polarization_left(self) -> None:
        if sd.get_state(self.polarization) == "ON":  # LEFT = ON
            raise sd.NoChangeError
        if sd.get_state(self.rf_ptt) == "ON":
            raise sd.PTTConflictError
        # brief cooldown
        time.sleep(SLEEP_TIMER)
        sd.power_on(self.polarization, self.polarization_pin)

    def polarization_right(self) -> None:
        if sd.get_state(self.polarization) == "OFF":  # RIGHT = OFF
            raise sd.NoChangeError
        if sd.get_state(self.rf_ptt) == "ON":
            raise sd.PTTConflictError
        # brief cooldown
        time.sleep(SLEEP_TIMER)
        sd.power_off(self.polarization, self.polarization_pin)


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
