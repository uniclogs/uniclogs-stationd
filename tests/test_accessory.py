import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAccessoryModuleStructure:
    """Test accessory module structure."""

    def test_accessory_file_exists(self):
        """Test that accessory.py exists."""
        accessory_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'accessory.py')
        assert os.path.exists(accessory_file)
