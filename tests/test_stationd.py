from stationd import stationd


class TestBasicFunctionality:
    """Test basic functionality without complex dependencies."""

    def test_stationd_module_imports(self) -> None:
        """Test that stationd module can be imported."""
        assert stationd is not None

    def test_stationd_has_expected_attributes(self) -> None:
        """Test that stationd module has expected classes and constants."""
        assert hasattr(stationd, 'StationD')
        assert hasattr(stationd, 'Command')
        assert hasattr(stationd, 'PersistFH')
        assert hasattr(stationd, 'config')

    def test_main_module_functionality(self) -> None:
        """Test that main module functionality is accessible."""
        from stationd import __main__
        assert __main__ is not None
