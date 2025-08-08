from stationd import accessory


class TestAccessoryModuleStructure:
    """Test accessory module structure."""

    def test_accessory_module_imports(self) -> None:
        """Test that accessory module can be imported from stationd."""
        assert accessory is not None
