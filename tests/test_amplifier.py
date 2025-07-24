import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAmplifierModuleStructure:
    """Test amplifier module structure."""

    def test_amplifier_file_exists(self):
        """Test that amplifier.py exists."""
        amplifier_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'amplifier.py')
        assert os.path.exists(amplifier_file)
