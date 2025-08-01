from stationd import amplifier


class TestAmplifierModuleStructure:
    """Test amplifier module structure."""

    def test_amplifier_file_exists(self) -> None:
        """Test that amplifier.py exists."""
        assert amplifier is not None
