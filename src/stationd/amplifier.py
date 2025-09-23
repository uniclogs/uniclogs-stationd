import time

import gpiod

from . import stationd as sd

MOLLY_TIME = 20  # In seconds
PTT_COOLDOWN = 120  # In seconds
SLEEP_TIMER = 0.1

# Polarization directions
LEFT = gpiod.line.Value.ACTIVE
RIGHT = gpiod.line.Value.INACTIVE


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
    """Controls for a tx-only amplifier.

    This class provides common functionality for controlling RF amplifiers
    That have a RF PTT (Push-To-Talk) switch and a power amplifier (PA).
    """

    def __init__(self, active_ptt: 'sd.ActivePTT', section: str) -> None:
        """Initialize a new Amplifier instance."""
        self.active_ptt = active_ptt
        self.section = section

        # Set up GPIO pins from config
        rf_ptt_chip, rf_ptt_pin = sd.config[section]['rf_ptt_pin'].split(' ')
        self.rf_ptt = sd.LineOut(f"/dev/gpiochip{rf_ptt_chip}", int(rf_ptt_pin))
        self.rf_ptt.value = gpiod.line.Value.INACTIVE

        pa_power_chip, pa_power_pin = sd.config[section]['pa_power_pin'].split(' ')
        self.pa_power = sd.LineOut(f"/dev/gpiochip{pa_power_chip}", int(pa_power_pin))
        self.pa_power.value = gpiod.line.Value.INACTIVE

        self.molly_guard_time = time.time() - MOLLY_TIME
        self.ptt_off_time = time.time() - PTT_COOLDOWN

    def device_status(self, command: list[str]) -> str:
        rf_ptt_state = 'ON' if self.rf_ptt.value == gpiod.line.Value.ACTIVE else 'OFF'
        pa_power_state = 'ON' if self.pa_power.value == gpiod.line.Value.ACTIVE else 'OFF'
        return f'{command[0]} rf-ptt {rf_ptt_state}\n{command[0]} pa-power {pa_power_state}\n'

    def component_status(self, command: list[str]) -> str:
        component_name = command[1].replace('-', '_')

        if component_name == 'rf_ptt':
            state = 'ON' if self.rf_ptt.value == gpiod.line.Value.ACTIVE else 'OFF'
            return f'{command[0]} {command[1]} {state}\n'
        if component_name == 'pa_power':
            state = 'ON' if self.pa_power.value == gpiod.line.Value.ACTIVE else 'OFF'
            return f'{command[0]} {command[1]} {state}\n'
        raise sd.InvalidCommandError

    def check_molly_guard(self) -> None:
        if time.time() - self.molly_guard_time > MOLLY_TIME:
            self.molly_guard_time = time.time()
            raise MollyGuardError(MOLLY_TIME)

    def rf_ptt_on(self) -> None:
        if self.rf_ptt.value == gpiod.line.Value.ACTIVE:
            raise sd.NoChangeError
        if self.pa_power.value == gpiod.line.Value.INACTIVE:
            raise sd.PTTConflictError

        # brief cooldown
        time.sleep(SLEEP_TIMER)
        self.active_ptt.inc()

        self.rf_ptt.value = gpiod.line.Value.ACTIVE

    def rf_ptt_off(self) -> None:
        if self.rf_ptt.value == gpiod.line.Value.INACTIVE:
            raise sd.NoChangeError

        self.rf_ptt.value = gpiod.line.Value.INACTIVE

        #  set time ptt turned off
        self.ptt_off_time = time.time()
        self.active_ptt.dec()

    def pa_power_on(self) -> None:
        if self.pa_power.value == gpiod.line.Value.ACTIVE:
            raise sd.NoChangeError
        self.check_molly_guard()

        self.pa_power.value = gpiod.line.Value.ACTIVE

    def pa_power_off(self) -> None:
        if self.pa_power.value == gpiod.line.Value.INACTIVE:
            raise sd.NoChangeError
        if self.rf_ptt.value == gpiod.line.Value.ACTIVE:
            raise sd.PTTConflictError
        #  Check PTT off for at least 2 minutes
        diff_sec = time.time() - self.ptt_off_time
        if diff_sec <= PTT_COOLDOWN:
            raise PTTCooldownError(round(PTT_COOLDOWN - diff_sec))

        self.pa_power.value = gpiod.line.Value.INACTIVE


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

        # Set up additional GPIO pins from config
        tr_relay_chip, tr_relay_pin = sd.config[section]['tr_relay_pin'].split(' ')
        self.tr_relay = sd.LineOut(f"/dev/gpiochip{tr_relay_chip}", int(tr_relay_pin))
        self.tr_relay.value = gpiod.line.Value.INACTIVE

        lna_chip, lna_pin = sd.config[section]['lna_pin'].split(' ')
        self.lna = sd.LineOut(f"/dev/gpiochip{lna_chip}", int(lna_pin))
        self.lna.value = gpiod.line.Value.INACTIVE

        polarization_chip, polarization_pin = sd.config[section]['polarization_pin'].split(' ')
        self.polarization = sd.LineOut(f"/dev/gpiochip{polarization_chip}", int(polarization_pin))
        self.polarization.value = RIGHT

    def device_status(self, command: list[str]) -> str:
        p_state = "LEFT" if self.polarization.value == LEFT else "RIGHT"
        tr_relay_state = 'ON' if self.tr_relay.value == gpiod.line.Value.ACTIVE else 'OFF'
        lna_state = 'ON' if self.lna.value == gpiod.line.Value.ACTIVE else 'OFF'

        return super().device_status(command) + (
            f'{command[0]} tr-relay {tr_relay_state}\n'
            f'{command[0]} lna {lna_state}\n'
            f'{command[0]} polarization {p_state}\n'
        )

    def component_status(self, command: list[str]) -> str:
        if command[1] == "polarization":
            p_state = "LEFT" if self.polarization.value == LEFT else "RIGHT"
            return f'{command[0]} {command[1]} {p_state}\n'

        component_name = command[1].replace('-', '_')

        if component_name == 'tr_relay':
            state = 'ON' if self.tr_relay.value == gpiod.line.Value.ACTIVE else 'OFF'
            return f'{command[0]} {command[1]} {state}\n'
        if component_name == 'lna':
            state = 'ON' if self.lna.value == gpiod.line.Value.ACTIVE else 'OFF'
            return f'{command[0]} {command[1]} {state}\n'

        return super().component_status(command)

    def rf_ptt_on(self) -> None:
        super().rf_ptt_on()
        # Enforce tr-relay and ptt are same state
        self.tr_relay_on()
        # Ptt command received, turn off LNA
        if self.lna.value == gpiod.line.Value.ACTIVE:
            self.lna.value = gpiod.line.Value.INACTIVE

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
        if self.tr_relay.value == gpiod.line.Value.ACTIVE:
            return
        self.tr_relay.value = gpiod.line.Value.ACTIVE

    def tr_relay_off(self) -> None:
        if self.tr_relay.value == gpiod.line.Value.INACTIVE:
            return
        self.tr_relay.value = gpiod.line.Value.INACTIVE

    def lna_on(self) -> None:
        if self.lna.value == gpiod.line.Value.ACTIVE:
            raise sd.NoChangeError
        #  Fail if PTT is on
        if self.rf_ptt.value == gpiod.line.Value.ACTIVE:
            raise sd.PTTConflictError
        self.lna.value = gpiod.line.Value.ACTIVE

    def lna_off(self) -> None:
        if self.lna.value == gpiod.line.Value.INACTIVE:
            raise sd.NoChangeError
        self.lna.value = gpiod.line.Value.INACTIVE

    def polarization_left(self) -> None:
        if self.polarization.value == LEFT:
            raise sd.NoChangeError
        if self.rf_ptt.value == gpiod.line.Value.ACTIVE:
            raise sd.PTTConflictError
        # brief cooldown
        time.sleep(SLEEP_TIMER)
        self.polarization.value = LEFT

    def polarization_right(self) -> None:
        if self.polarization.value == RIGHT:
            raise sd.NoChangeError
        if self.rf_ptt.value == gpiod.line.Value.ACTIVE:
            raise sd.PTTConflictError
        # brief cooldown
        time.sleep(SLEEP_TIMER)
        self.polarization.value = RIGHT


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
