"""GPIO Management System.

This module handles GPIO chip, pin, and line allocation tracking.
"""

import logging
import configparser
from typing import Dict, List, Tuple, Optional

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
        self.chips: Dict[str, gpiod.Chip] = {}
        self.available_pins: Dict[str, Tuple[str, int, gpiod.LineRequest]] = {}
        self.allocated_pins: Dict[str, List[Tuple[str, gpiod.LineRequest]]] = {}
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
                        config={
                            pin_num: gpiod.LineSettings(direction=gpiod.line.Direction.OUTPUT)
                        }
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
                        # Pin already allocated to this device, return existing line request
                        logger.warning(f"Pin '{pin_label}' already allocated to device '{device_name}'")
                        return next(line_req for p_label, line_req in allocated_pins if p_label == pin_label)
                    else:
                        raise RuntimeError(
                            f"Pin '{pin_label}' is already allocated to device '{allocated_device}'"
                        )

        # FIXME: Remove pin from "available pins"?
        chip_path, pin_number, line_request = self.available_pins[pin_label]

        # Allocate
        if device_name not in self.allocated_pins:
            self.allocated_pins[device_name] = []
        self.allocated_pins[device_name].append((pin_label, line_request))

        logger.info(f"Allocated pin '{pin_label}' ({chip_path}:{pin_number}) to device '{device_name}'")

        return line_request

    def get_pin_info(self, pin_label: str) -> Optional[Tuple[str, int]]:
        """Get chip path and pin number for a given pin name."""
        if pin_label in self.available_pins:
            chip_path, pin_number, _ = self.available_pins[pin_label]
            return (chip_path, pin_number)
        return None
