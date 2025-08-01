import time
from datetime import UTC, datetime
from multiprocessing import Manager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from multiprocessing.managers import DictProxy

from . import stationd as sd
from .gpio.gpio import GPIOPin


class Amplifier:
    """Base class for RF amplifier control systems.

    This class provides common functionality for controlling RF amplifiers
    including transmit/receive relay control, RF PTT (Push-To-Talk), power
    amplifier control, LNA (Low Noise Amplifier) control, and antenna
    polarization switching.
    """

    def __init__(self) -> None:
        """Initialize a new Amplifier instance.

        The specific GPIO pins will be configured by subclasses.
        """
        self.name: str | None = None
        self.tr_relay: GPIOPin | None = None
        self.rf_ptt: GPIOPin | None = None
        self.pa_power: GPIOPin | None = None
        self.lna: GPIOPin | None = None
        self.polarization: GPIOPin | None = None
        self.molly_guard_time: datetime | None = None

        # Shared data
        self.manager: Manager = Manager()
        self.shared: DictProxy[str, Any] = self.manager.dict()
        self.shared['ptt_off_time'] = datetime.now(tz=UTC)


    def device_status(self, command_obj: 'sd.Command') -> None:
        p_state = 'LEFT' if sd.get_state(self.polarization) == 'ON' else 'RIGHT'
        status = (
            f'{command_obj.command[0]} tr-relay {sd.get_state(self.tr_relay)}\n'
            f'{command_obj.command[0]} rf-ptt {sd.get_state(self.rf_ptt)}\n'
            f'{command_obj.command[0]} pa-power {sd.get_state(self.pa_power)}\n'
            f'{command_obj.command[0]} lna {sd.get_state(self.lna)}\n'
            f'{command_obj.command[0]} polarization {p_state}\n'
        )
        sd.status_response(command_obj, status)


    def component_status(self, command_obj: 'sd.Command') -> None:
        try:
            component = getattr(self, command_obj.command[1].replace('-', '_'))
            if command_obj.command[1] == 'polarization':
                p_state = 'LEFT' if sd.get_state(self.polarization) == 'ON' else 'RIGHT'
                status = f'{command_obj.command[0]} {command_obj.command[1]} {p_state}\n'
                sd.status_response(command_obj, status)
            else:
                status = sd.get_status(component, command_obj)
                sd.status_response(command_obj, status)
        except AttributeError as error:
            raise sd.InvalidCommandError(command_obj) from error


    def molly_guard(self, command_obj: 'sd.Command') -> bool:
        diff_sec = sd.calculate_diff_sec(self.molly_guard_time)
        if diff_sec is None or diff_sec > 20:
            self.molly_guard_time = datetime.now(tz=UTC)
            raise sd.MollyGuardError(command_obj)
        # reset timer to none
        self.molly_guard_time = None
        return True


    def tr_relay_on(self) -> None:
        if self.tr_relay.read() is sd.ON:
            return
        self.tr_relay.write(sd.ON)


    def tr_relay_off(self) -> None:
        if self.tr_relay.read() is sd.OFF:
            return
        self.tr_relay.write(sd.OFF)


    def rf_ptt_on(self, command_obj: 'sd.Command') -> None:
        if self.rf_ptt.read() is sd.ON:
            sd.no_change_response(command_obj)
            return
        if self.pa_power.read() is sd.OFF:
            raise sd.PTTConflictError(command_obj)
        if command_obj.num_active_ptt >= sd.PTT_MAX_COUNT:
            raise sd.MaxPTTError(command_obj)
        # Enforce tr-relay and ptt are same state
        if self.tr_relay is not None:
            self.tr_relay_on(command_obj)

        # Ptt command received, turn off LNA
        if self.lna is not None:
            self.lna_off(command_obj)
        # brief cooldown
        time.sleep(sd.SLEEP_TIMER)
        self.rf_ptt.write(sd.ON)
        sd.success_response(command_obj)
        command_obj.num_active_ptt += 1


    def rf_ptt_off(self, command_obj: 'sd.Command') -> None:
        if self.rf_ptt.read() is sd.OFF:
            sd.no_change_response(command_obj)
            return
        self.rf_ptt.write(sd.OFF)
        sd.success_response(command_obj)
        #  set time ptt turned off
        self.shared['ptt_off_time'] = datetime.now(tz=UTC)
        command_obj.num_active_ptt -= 1
        # make sure num_active_ptt never falls below 0
        command_obj.num_active_ptt = max(command_obj.num_active_ptt, 0)
        # Enforce tr-relay and ptt are same state
        if self.tr_relay is not None:
            self.tr_relay_off(command_obj)


    def pa_power_on(self, command_obj: 'sd.Command') -> None:
        if self.pa_power.read() is sd.ON:
            sd.no_change_response(command_obj)
            return
        if self.molly_guard(command_obj):
            if self.tr_relay is not None:
                self.tr_relay_on(command_obj)
            self.pa_power.write(sd.ON)
            sd.success_response(command_obj)


    def pa_power_off(self, command_obj: 'sd.Command') -> None:
        if self.pa_power.read() is sd.OFF:
            sd.no_change_response(command_obj)
            return
        if self.rf_ptt.read() is sd.ON:
            raise sd.PTTConflictError(command_obj)
        #  Check PTT off for at least 2 minutes
        diff_sec = sd.calculate_diff_sec(self.shared['ptt_off_time'])
        if diff_sec > sd.PTT_COOLDOWN:
            if self.tr_relay is not None:
                self.tr_relay_off(command_obj)
            self.pa_power.write(sd.OFF)
            sd.success_response(command_obj)
        else:
            raise sd.PTTCooldownError(round(sd.PTT_COOLDOWN - diff_sec))


    def lna_on(self, command_obj: 'sd.Command') -> None:
        if self.lna.read() is sd.ON:
            sd.no_change_response(command_obj)
            return
        #  Fail if PTT is on
        if self.rf_ptt.read() is sd.ON:
            raise sd.PTTConflictError(command_obj)
        self.lna.write(sd.ON)
        sd.success_response(command_obj)


    def lna_off(self, command_obj: 'sd.Command') -> None:
        # only send response if called directly via command
        if self.lna.read() is sd.OFF and command_obj.command[1] == 'lna':
            sd.no_change_response(command_obj)
            return
        self.lna.write(sd.OFF)
        # only send response if called directly via command
        if command_obj.command[1] == 'lna':
            sd.success_response(command_obj)


    def polarization_left(self, command_obj: 'sd.Command') -> None:
        if self.polarization.read() is sd.LEFT:
            sd.no_change_response(command_obj)
            return
        if self.rf_ptt.read() is sd.ON:
            raise sd.PTTConflictError(command_obj)
        # brief cooldown
        time.sleep(sd.SLEEP_TIMER)
        self.polarization.write(sd.LEFT)
        sd.success_response(command_obj)


    def polarization_right(self, command_obj: 'sd.Command') -> None:
        if self.polarization.read() is sd.RIGHT:
            sd.no_change_response(command_obj)
            return
        if self.rf_ptt.read() is sd.ON:
            raise sd.PTTConflictError(command_obj)
        # brief cooldown
        time.sleep(sd.SLEEP_TIMER)
        self.polarization.write(sd.RIGHT)
        sd.success_response(command_obj)


class VHF(Amplifier):
    """VHF amplifier control.

    Controls VHF band RF amplifier including transmit/receive relay, RF PTT,
    power amplifier, LNA, and polarization switching. Configured for VHF
    frequency band operation.
    """

    def __init__(self) -> None:
        """Initialize the VHF amplifier.

        Sets up the VHF amplifier with all its GPIO control pins.
        """
        super().__init__()
        self.name = 'VHF'
        self.tr_relay = sd.assert_out(
            GPIOPin(
                int(sd.config['VHF']['tr_relay_pin']),
                None,
                initial=None
            )
        )
        self.rf_ptt = sd.assert_out(
            GPIOPin(
                int(sd.config['VHF']['rf_ptt_pin']),
                None,
                initial=None
            )
        )
        self.pa_power = sd.assert_out(
            GPIOPin(
                int(sd.config['VHF']['pa_power_pin']),
                None,
                initial=None
            )
        )
        self.lna = sd.assert_out(
            GPIOPin(
                int(sd.config['VHF']['lna_pin']),
                None,
                initial=None
            )
        )
        self.polarization = sd.assert_out(
            GPIOPin(
                int(sd.config['VHF']['polarization_pin']),
                None,
                initial=None
            )
        )


class UHF(Amplifier):
    """UHF amplifier control.

    Controls UHF band RF amplifier including transmit/receive relay, RF PTT,
    power amplifier, LNA, and polarization switching. Configured for UHF
    frequency band operation.
    """

    def __init__(self) -> None:
        """Initialize the UHF amplifier.

        Sets up the UHF amplifier with all its GPIO control pins.
        """
        super().__init__()
        self.name = 'UHF'
        self.tr_relay = sd.assert_out(
            GPIOPin(
                int(sd.config['UHF']['tr_relay_pin']),
                None,
                initial=None
            )
        )
        self.rf_ptt = sd.assert_out(
            GPIOPin(
                int(sd.config['UHF']['rf_ptt_pin']),
                None,
                initial=None
            )
        )
        self.pa_power = sd.assert_out(
            GPIOPin(
                int(sd.config['UHF']['pa_power_pin']),
                None,
                initial=None
            )
        )
        self.lna = sd.assert_out(
            GPIOPin(
                int(sd.config['UHF']['lna_pin']),
                None,
                initial=None
            )
        )
        self.polarization = sd.assert_out(
            GPIOPin(
                int(sd.config['UHF']['polarization_pin']),
                None,
                initial=None
            )
        )


class LBand(Amplifier):
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
        super().__init__()
        self.name = 'L-Band'
        self.rf_ptt = sd.assert_out(
            GPIOPin(
                int(sd.config['L-BAND']['rf_ptt_pin']),
                None,
                initial=None
            )
        )
        self.pa_power = sd.assert_out(
            GPIOPin(
                int(sd.config['L-BAND']['pa_power_pin']),
                None,
                initial=None
            )
        )
