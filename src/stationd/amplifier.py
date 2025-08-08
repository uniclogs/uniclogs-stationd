import time

from . import stationd as sd
from .gpio.gpio import HIGH, LOW, GPIOPin

MOLLY_TIME = 20  # In seconds
PTT_COOLDOWN = 120  # In seconds
SLEEP_TIMER = 0.1

LEFT = HIGH
RIGHT = LOW


class MollyGuardError(Exception):
    """Exception raised when molly guard protection is triggered.

    Used to prevent accidental execution of potentially dangerous commands by
    requiring confirmation within a time window.
    """


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

    def __init__(self, active_ptt: 'sd.ActivePTT', rf_ptt_pin: int, pa_power_pin: int) -> None:
        """Initialize a new Amplifier instance."""
        self.active_ptt = active_ptt
        self.rf_ptt = sd.assert_out(GPIOPin(rf_ptt_pin, None, initial=None))
        self.pa_power = sd.assert_out(GPIOPin(pa_power_pin, None, initial=None))

        self.molly_guard_time = time.time() - MOLLY_TIME
        self.ptt_off_time = time.time() - PTT_COOLDOWN

    def device_status(self, command: list[str]) -> str:
        return (
            f'{command[0]} rf-ptt {sd.get_state(self.rf_ptt)}\n'
            f'{command[0]} pa-power {sd.get_state(self.pa_power)}\n'
        )

    def component_status(self, command: list[str]) -> str:
        try:
            component = getattr(self, command[1].replace('-', '_'))
        except AttributeError as error:
            raise sd.InvalidCommandError from error

        return sd.get_status(component, command)

    def check_molly_guard(self) -> None:
        if time.time() - self.molly_guard_time > MOLLY_TIME:
            self.molly_guard_time = time.time()
            raise MollyGuardError

    def rf_ptt_on(self) -> None:
        if self.rf_ptt.read() == sd.ON:
            raise sd.NoChangeError
        if self.pa_power.read() == sd.OFF:
            raise sd.PTTConflictError

        # brief cooldown
        time.sleep(SLEEP_TIMER)
        self.active_ptt.inc()
        self.rf_ptt.write(sd.ON)

    def rf_ptt_off(self) -> None:
        if self.rf_ptt.read() == sd.OFF:
            raise sd.NoChangeError
        self.rf_ptt.write(sd.OFF)
        #  set time ptt turned off
        self.ptt_off_time = time.time()
        self.active_ptt.dec()

    def pa_power_on(self) -> None:
        if self.pa_power.read() == sd.ON:
            raise sd.NoChangeError
        self.check_molly_guard()
        self.pa_power.write(sd.ON)

    def pa_power_off(self) -> None:
        if self.pa_power.read() == sd.OFF:
            raise sd.NoChangeError
        if self.rf_ptt.read() == sd.ON:
            raise sd.PTTConflictError
        #  Check PTT off for at least 2 minutes
        diff_sec = time.time() - self.ptt_off_time
        if diff_sec <= PTT_COOLDOWN:
            raise PTTCooldownError(round(PTT_COOLDOWN - diff_sec))
        self.pa_power.write(sd.OFF)


class RxTxAmplifier(TxAmplifier):
    """Controls for a channel with both TX and RX amplifiers.

    This class provides common functionality for controlling RF amplifiers
    including transmit/receive relay control, RF PTT (Push-To-Talk), power
    amplifier control, LNA (Low Noise Amplifier) control, and antenna
    polarization switching.
    """

    def __init__(  # noqa: PLR0913
        self,
        active_ptt: 'sd.ActivePTT',
        rf_ptt_pin: int,
        pa_power_pin: int,
        tr_relay_pin: int,
        lna_pin: int,
        polarization_pin: int,
    ) -> None:
        """Initialize a new Amplifier instance."""
        super().__init__(active_ptt, rf_ptt_pin, pa_power_pin)
        self.tr_relay = sd.assert_out(GPIOPin(tr_relay_pin, None, initial=None))
        self.lna = sd.assert_out(GPIOPin(lna_pin, None, initial=None))
        self.polarization = sd.assert_out(GPIOPin(polarization_pin, None, initial=None))

    def device_status(self, command: list[str]) -> str:
        p_state = 'LEFT' if self.polarization.read() == LEFT else 'RIGHT'
        return super().device_status(command) + (
            f'{command[0]} tr-relay {sd.get_state(self.tr_relay)}\n'
            f'{command[0]} lna {sd.get_state(self.lna)}\n'
            f'{command[0]} polarization {p_state}\n'
        )

    def component_status(self, command: list[str]) -> str:
        if command[1] == 'polarization':
            p_state = 'LEFT' if self.polarization.read() == LEFT else 'RIGHT'
            return f'{command[0]} {command[1]} {p_state}\n'
        return super().component_status(command)

    def rf_ptt_on(self) -> None:
        super().rf_ptt_on()
        # Enforce tr-relay and ptt are same state
        self.tr_relay_on()
        # Ptt command received, turn off LNA
        if self.lna.read() != sd.OFF:
            self.lna.write(sd.OFF)

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
        if self.tr_relay.read() == sd.ON:
            return
        self.tr_relay.write(sd.ON)

    def tr_relay_off(self) -> None:
        if self.tr_relay.read() == sd.OFF:
            return
        self.tr_relay.write(sd.OFF)

    def lna_on(self) -> None:
        if self.lna.read() == sd.ON:
            raise sd.NoChangeError
        #  Fail if PTT is on
        if self.rf_ptt.read() == sd.ON:
            raise sd.PTTConflictError
        self.lna.write(sd.ON)

    def lna_off(self) -> None:
        if self.lna.read() == sd.OFF:
            raise sd.NoChangeError
        self.lna.write(sd.OFF)

    def polarization_left(self) -> None:
        if self.polarization.read() == LEFT:
            raise sd.NoChangeError
        if self.rf_ptt.read() == sd.ON:
            raise sd.PTTConflictError
        # brief cooldown
        time.sleep(SLEEP_TIMER)
        self.polarization.write(LEFT)

    def polarization_right(self) -> None:
        if self.polarization.read() == RIGHT:
            raise sd.NoChangeError
        if self.rf_ptt.read() == sd.ON:
            raise sd.PTTConflictError
        # brief cooldown
        time.sleep(SLEEP_TIMER)
        self.polarization.write(RIGHT)


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
        super().__init__(
            active_ptt,
            rf_ptt_pin=int(sd.config['VHF']['rf_ptt_pin']),
            pa_power_pin=int(sd.config['VHF']['pa_power_pin']),
            tr_relay_pin=int(sd.config['VHF']['tr_relay_pin']),
            lna_pin=int(sd.config['VHF']['lna_pin']),
            polarization_pin=int(sd.config['VHF']['polarization_pin']),
        )


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
        super().__init__(
            active_ptt,
            rf_ptt_pin=int(sd.config['UHF']['rf_ptt_pin']),
            pa_power_pin=int(sd.config['UHF']['pa_power_pin']),
            tr_relay_pin=int(sd.config['UHF']['tr_relay_pin']),
            lna_pin=int(sd.config['UHF']['lna_pin']),
            polarization_pin=int(sd.config['UHF']['polarization_pin']),
        )


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
        super().__init__(
            active_ptt,
            rf_ptt_pin=int(sd.config['L-BAND']['rf_ptt_pin']),
            pa_power_pin=int(sd.config['L-BAND']['pa_power_pin']),
        )
