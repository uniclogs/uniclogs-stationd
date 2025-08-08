import time

from . import stationd as sd
from .gpio.gpio import HIGH, LOW, GPIOPin

MOLLY_TIME = 20  # In seconds
PTT_COOLDOWN = 120  # In seconds
SLEEP_TIMER = 0.1
PTT_MAX_COUNT = 1

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


class MaxPTTError(Exception):
    """Exception raised when maximum PTT connections are exceeded.

    Prevents exceeding the configured maximum number of simultaneous PTT
    connections.
    """


class TxAmplifier:
    """Controls for a TX only amplifier.

    This class provides common functionality for controlling RF amplifiers
    That have a RF PTT (Push-To-Talk) switch and a power amplifier (PA).
    """

    def __init__(self, rf_ptt_pin: int, pa_power_pin: int) -> None:
        """Initialize a new Amplifier instance."""
        self.rf_ptt = sd.assert_out(GPIOPin(rf_ptt_pin, None, initial=None))
        self.pa_power = sd.assert_out(GPIOPin(pa_power_pin, None, initial=None))

        self.molly_guard_time = time.time() - MOLLY_TIME
        self.ptt_off_time = time.time() - PTT_COOLDOWN

    def device_status(self, command_obj: 'sd.Command') -> None:
        status = (
            f'{command_obj.command[0]} rf-ptt {sd.get_state(self.rf_ptt)}\n'
            f'{command_obj.command[0]} pa-power {sd.get_state(self.pa_power)}\n'
        )
        sd.status_response(command_obj, status)

    def component_status(self, command_obj: 'sd.Command') -> None:
        try:
            component = getattr(self, command_obj.command[1].replace('-', '_'))
        except AttributeError as error:
            raise sd.InvalidCommandError(command_obj) from error

        status = sd.get_status(component, command_obj)
        sd.status_response(command_obj, status)

    def molly_guard(self, command_obj: 'sd.Command') -> bool:
        if time.time() - self.molly_guard_time > MOLLY_TIME:
            self.molly_guard_time = time.time()
            raise MollyGuardError(command_obj)
        return True

    def rf_ptt_on(self, command_obj: 'sd.Command') -> None:
        if self.rf_ptt.read() == sd.ON:
            raise sd.NoChangeError
        if self.pa_power.read() == sd.OFF:
            raise sd.PTTConflictError(command_obj)
        if command_obj.num_active_ptt >= PTT_MAX_COUNT:
            raise MaxPTTError(command_obj)

        # brief cooldown
        time.sleep(SLEEP_TIMER)
        self.rf_ptt.write(sd.ON)
        sd.success_response(command_obj)
        command_obj.num_active_ptt += 1

    def rf_ptt_off(self, command_obj: 'sd.Command') -> None:
        if self.rf_ptt.read() == sd.OFF:
            raise sd.NoChangeError
        self.rf_ptt.write(sd.OFF)
        sd.success_response(command_obj)
        #  set time ptt turned off
        self.ptt_off_time = time.time()
        # make sure num_active_ptt never falls below 0
        command_obj.num_active_ptt = max(command_obj.num_active_ptt - 1, 0)

    def pa_power_on(self, command_obj: 'sd.Command') -> None:
        if self.pa_power.read() == sd.ON:
            raise sd.NoChangeError
        if self.molly_guard(command_obj):
            self.pa_power.write(sd.ON)
            sd.success_response(command_obj)

    def pa_power_off(self, command_obj: 'sd.Command') -> None:
        if self.pa_power.read() == sd.OFF:
            raise sd.NoChangeError
        if self.rf_ptt.read() == sd.ON:
            raise sd.PTTConflictError(command_obj)
        #  Check PTT off for at least 2 minutes
        diff_sec = time.time() - self.ptt_off_time
        if diff_sec > PTT_COOLDOWN:
            self.pa_power.write(sd.OFF)
            sd.success_response(command_obj)
        else:
            raise PTTCooldownError(round(PTT_COOLDOWN - diff_sec))


class RxTxAmplifier(TxAmplifier):
    """Controls for a channel with both TX and RX amplifiers.

    This class provides common functionality for controlling RF amplifiers
    including transmit/receive relay control, RF PTT (Push-To-Talk), power
    amplifier control, LNA (Low Noise Amplifier) control, and antenna
    polarization switching.
    """

    def __init__(
        self,
        rf_ptt_pin: int,
        pa_power_pin: int,
        tr_relay_pin: int,
        lna_pin: int,
        polarization_pin: int,
    ) -> None:
        """Initialize a new Amplifier instance."""
        super().__init__(rf_ptt_pin, pa_power_pin)
        self.tr_relay = sd.assert_out(GPIOPin(tr_relay_pin, None, initial=None))
        self.lna = sd.assert_out(GPIOPin(lna_pin, None, initial=None))
        self.polarization = sd.assert_out(GPIOPin(polarization_pin, None, initial=None))

    def device_status(self, command_obj: 'sd.Command') -> None:
        p_state = 'LEFT' if self.polarization.read() == LEFT else 'RIGHT'
        status = (
            f'{command_obj.command[0]} tr-relay {sd.get_state(self.tr_relay)}\n'
            f'{command_obj.command[0]} rf-ptt {sd.get_state(self.rf_ptt)}\n'
            f'{command_obj.command[0]} pa-power {sd.get_state(self.pa_power)}\n'
            f'{command_obj.command[0]} lna {sd.get_state(self.lna)}\n'
            f'{command_obj.command[0]} polarization {p_state}\n'
        )
        sd.status_response(command_obj, status)

    def component_status(self, command_obj: 'sd.Command') -> None:
        if command_obj.command[1] == 'polarization':
            p_state = 'LEFT' if self.polarization.read() == LEFT else 'RIGHT'
            status = f'{command_obj.command[0]} {command_obj.command[1]} {p_state}\n'
            sd.status_response(command_obj, status)
        else:
            super().component_status(command_obj)

    def rf_ptt_on(self, command_obj: 'sd.Command') -> None:
        super().rf_ptt_on(command_obj)
        # Enforce tr-relay and ptt are same state
        self.tr_relay_on()
        # Ptt command received, turn off LNA
        if self.lna.read() != sd.OFF:
            self.lna.write(sd.OFF)

    def rf_ptt_off(self, command_obj: 'sd.Command') -> None:
        super().rf_ptt_off(command_obj)
        # Enforce tr-relay and ptt are same state
        self.tr_relay_off()

    def pa_power_on(self, command_obj: 'sd.Command') -> None:
        super().pa_power_on(command_obj)
        self.tr_relay_on()

    def pa_power_off(self, command_obj: 'sd.Command') -> None:
        super().pa_power_off(command_obj)
        self.tr_relay_off()

    def tr_relay_on(self) -> None:
        if self.tr_relay.read() == sd.ON:
            return
        self.tr_relay.write(sd.ON)

    def tr_relay_off(self) -> None:
        if self.tr_relay.read() == sd.OFF:
            return
        self.tr_relay.write(sd.OFF)

    def lna_on(self, command_obj: 'sd.Command') -> None:
        if self.lna.read() == sd.ON:
            raise sd.NoChangeError
        #  Fail if PTT is on
        if self.rf_ptt.read() == sd.ON:
            raise sd.PTTConflictError(command_obj)
        self.lna.write(sd.ON)
        sd.success_response(command_obj)

    def lna_off(self, command_obj: 'sd.Command') -> None:
        if self.lna.read() == sd.OFF:
            raise sd.NoChangeError
        self.lna.write(sd.OFF)
        sd.success_response(command_obj)

    def polarization_left(self, command_obj: 'sd.Command') -> None:
        if self.polarization.read() == LEFT:
            raise sd.NoChangeError
        if self.rf_ptt.read() == sd.ON:
            raise sd.PTTConflictError(command_obj)
        # brief cooldown
        time.sleep(SLEEP_TIMER)
        self.polarization.write(LEFT)
        sd.success_response(command_obj)

    def polarization_right(self, command_obj: 'sd.Command') -> None:
        if self.polarization.read() == RIGHT:
            raise sd.NoChangeError
        if self.rf_ptt.read() == sd.ON:
            raise sd.PTTConflictError(command_obj)
        # brief cooldown
        time.sleep(SLEEP_TIMER)
        self.polarization.write(RIGHT)
        sd.success_response(command_obj)


class VHF(RxTxAmplifier):
    """VHF amplifier control.

    Controls VHF band RF amplifier including transmit/receive relay, RF PTT,
    power amplifier, LNA, and polarization switching. Configured for VHF
    frequency band operation.
    """

    def __init__(self) -> None:
        """Initialize the VHF amplifier.

        Sets up the VHF amplifier with all its GPIO control pins.
        """
        super().__init__(
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

    def __init__(self) -> None:
        """Initialize the UHF amplifier.

        Sets up the UHF amplifier with all its GPIO control pins.
        """
        super().__init__(
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

    def __init__(self) -> None:
        """Initialize the L-Band amplifier.

        Sets up the L-Band amplifier with RF PTT and power amplifier GPIO
        control pins.

        Note: L-Band amplifier does not include TR relay, LNA, or polarization
              controls.
        """
        super().__init__(
            rf_ptt_pin=int(sd.config['L-BAND']['rf_ptt_pin']),
            pa_power_pin=int(sd.config['L-BAND']['pa_power_pin']),
        )
