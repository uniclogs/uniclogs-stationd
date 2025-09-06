"""GPIO Management System.

This module handles GPIO chip, pin, and line allocation tracking.
"""

import configparser
import logging

import gpiod

logger = logging.getLogger(__name__)


class GPIOAllocator:
    """Manages allocation of GPIO chips and pins for station devices.

    This class parses GPIO configuration from config.ini and provides
    pin allocation services to ensure no pin conflicts between devices.
    """

    def __init__(self, config: configparser.ConfigParser) -> None:
        """Initialize GPIO allocator with configuration."""
        self.config = config
        self.chips: dict[str, gpiod.Chip] = {}
        self.available_pins: dict[str, tuple[str, int, gpiod.LineRequest]] = {}
        self.allocated_pins: dict[str, list[tuple[str, gpiod.LineRequest]]] = {}
        self._parse_config()

    def _parse_config(self) -> None:
        """Parse configuration file and setup available GPIO chips / pins."""
        for chip_path in self.config.sections():
            if chip_path.startswith('/dev/gpiochip'):
                chip = gpiod.Chip(chip_path)
                self.chips[chip_path] = chip

                # Process the pins for the current chip
                for pin_label, pin_val in self.config[chip_path].items():
                    pin_num = int(pin_val)
                    line_request = chip.request_lines(
                        consumer="stationd",
                        config={pin_num: gpiod.LineSettings(direction=gpiod.line.Direction.OUTPUT)},
                    )

                    self.available_pins[pin_label] = (chip_path, pin_num, line_request)

    def allocate_pin(self, device_name: str, pin_label: str) -> gpiod.LineRequest:
        """Allocate a GPIO pin for a device."""
        # Check if pin exists in configuration
        if pin_label not in self.available_pins:
            raise ValueError(f"Pin '{pin_label}' not found.")

        # Check if pin is already allocated
        for allocated_device, allocated_pins in self.allocated_pins.items():
            for allocated_pin_label, _ in allocated_pins:
                if allocated_pin_label == pin_label:
                    if allocated_device == device_name:
                        logger.warning(
                            "Pin '%s' already in use by device '%s'", pin_label, device_name
                        )
                        return next(
                            line_req for p_label, line_req in allocated_pins if p_label == pin_label
                        )
                    raise RuntimeError(
                        f"Pin '{pin_label}' is already allocated to device '{allocated_device}'"
                    )

        # FIXME: Remove pin from "available pins"?
        chip_path, pin_number, line_request = self.available_pins[pin_label]

        # Allocate
        if device_name not in self.allocated_pins:
            self.allocated_pins[device_name] = []
        self.allocated_pins[device_name].append((pin_label, line_request))

        logger.info(
            "Allocated pin '%s' (%s:%s) to device '%s'",
            pin_label,
            chip_path,
            pin_number,
            device_name,
        )

        return line_request

    def get_pin_info(self, pin_label: str) -> tuple[str, int] | None:
        """Get chip path and pin number for a given pin name."""
        if pin_label in self.available_pins:
            chip_path, pin_number, _ = self.available_pins[pin_label]
            return (chip_path, pin_number)
        return None
