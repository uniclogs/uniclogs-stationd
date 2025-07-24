import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBasicFunctionality:
    """Test basic functionality without complex dependencies."""

    def test_main_file_exists(self):
        """Test that __main__.py exists and has expected content."""
        main_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '__main__.py')
        assert os.path.exists(main_file)

        with open(main_file, 'r') as f:
            content = f.read()
            assert 'import stationd' in content
            assert 'if __name__ == "__main__"' in content
            assert 'StationD()' in content


class TestProjectStructure:
    """Test project structure and files."""

    def test_project_files_exist(self):
        """Test that all expected project files exist."""
        project_root = os.path.dirname(os.path.dirname(__file__))

        expected_files = [
            '__main__.py',
            'stationd.py',
            'amplifier.py',
            'accessory.py',
            'pyproject.toml'
        ]

        for file_name in expected_files:
            file_path = os.path.join(project_root, file_name)
            assert os.path.exists(file_path), f"Expected file {file_name} not found"
