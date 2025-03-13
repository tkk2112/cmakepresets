import argparse
import json
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from rich.table import Table

from cmakepresets import cli
from cmakepresets.presets import CMakePresets

from .decorators import CMakePresets_json


@pytest.fixture(scope="function")  # type: ignore[misc]
def mock_console_print() -> Generator[MagicMock, None, None]:
    """Fixture to mock console.print to capture output."""
    with patch("cmakepresets.cli.console.print") as mock_print:
        yield mock_print


@pytest.fixture(scope="function")  # type: ignore[misc]
def mock_presets() -> MagicMock:
    """Fixture to create a mock CMakePresets instance."""
    presets = MagicMock(spec=CMakePresets)

    # Configure mock with some test data
    presets.configure_presets = [
        {"name": "default", "generator": "Ninja", "hidden": False, "default": True},
        {"name": "debug", "generator": "Ninja", "hidden": False},
        {"name": "hidden-preset", "generator": "Ninja", "hidden": True},
    ]

    presets.build_presets = [
        {"name": "default-build", "configurePreset": "default", "hidden": False},
        {"name": "debug-build", "configurePreset": "debug", "hidden": False, "default": True},
    ]

    presets.test_presets = [
        {"name": "default-test", "configurePreset": "default"},
    ]

    # Setup mock methods
    presets.get_preset_by_name.side_effect = lambda preset_type, name: next(
        (p for p in getattr(presets, f"{preset_type}_presets") if p.get("name") == name), None
    )

    # Setup preset tree for related commands
    preset_tree = {
        "default": {
            "preset": presets.configure_presets[0],
            "dependents": {
                "buildPresets": [presets.build_presets[0]],
                "testPresets": [presets.test_presets[0]],
            },
        },
        "debug": {
            "preset": presets.configure_presets[1],
            "dependents": {
                "buildPresets": [presets.build_presets[1]],
                "testPresets": [],
            },
        },
    }
    presets.get_preset_tree.return_value = preset_tree

    return presets


def test_create_parser() -> None:
    """Test that the argument parser is created with the expected subcommands."""
    parser = cli.create_parser()

    # Check parser is created
    assert isinstance(parser, argparse.ArgumentParser)

    # Check subparsers exist
    actions = parser._actions
    subparsers = next((action for action in actions if isinstance(action, argparse._SubParsersAction)), None)
    assert subparsers is not None

    # Verify subcommands
    choices = subparsers.choices
    assert "list" in choices
    assert "show" in choices
    assert "related" in choices


def test_get_presets_by_type(mock_presets: MagicMock) -> None:
    """Test getting presets of different types."""
    result = cli.get_presets_by_type(mock_presets, "configure")
    assert result == mock_presets.configure_presets

    result = cli.get_presets_by_type(mock_presets, "build")
    assert result == mock_presets.build_presets

    result = cli.get_presets_by_type(mock_presets, "test")
    assert result == mock_presets.test_presets

    # Test unknown type
    result = cli.get_presets_by_type(mock_presets, "unknown")
    assert result == []


def test_filter_presets() -> None:
    """Test filtering presets based on visibility."""
    presets = [
        {"name": "visible", "hidden": False},
        {"name": "hidden", "hidden": True},
    ]

    # Without showing hidden
    filtered = cli._filter_presets(presets, show_hidden=False)
    assert len(filtered) == 1
    assert filtered[0]["name"] == "visible"

    # With showing hidden
    filtered = cli._filter_presets(presets, show_hidden=True)
    assert len(filtered) == 2


def test_handle_list_command_flat(mock_presets: MagicMock, mock_console_print: MagicMock) -> None:
    """Test the list command with flat output."""
    args = argparse.Namespace(flat=True, type="configure", show_hidden=False)

    result = cli.handle_list_command(mock_presets, args)

    assert result == 0
    mock_console_print.assert_called()

    # Check at least one call contains the preset name
    any_call_contains_name = any("default" in str(call) for call in mock_console_print.call_args_list)
    assert any_call_contains_name


def test_handle_list_command_tabular(mock_presets: MagicMock, mock_console_print: MagicMock) -> None:
    """Test the list command with tabular output."""
    args = argparse.Namespace(flat=False, type="all", show_hidden=False)

    result = cli.handle_list_command(mock_presets, args)

    assert result == 0
    mock_console_print.assert_called_once()

    # First argument should be a table
    table_arg = mock_console_print.call_args[0][0]
    assert isinstance(table_arg, Table)


def test_handle_show_command(mock_presets: MagicMock, mock_console_print: MagicMock) -> None:
    """Test the show command."""
    # Mock flatten_preset to return a simple dict
    mock_presets.flatten_preset.return_value = {"name": "default", "generator": "Ninja", "cacheVariables": {"CMAKE_BUILD_TYPE": "Debug"}}

    # Test with found preset
    args = argparse.Namespace(preset_name="default", type="configure", json=False, flatten=False)
    result = cli.handle_show_command(mock_presets, args)

    assert result == 0
    mock_console_print.assert_called()

    # Test with JSON output
    mock_console_print.reset_mock()
    args = argparse.Namespace(preset_name="default", type="configure", json=True, flatten=False)
    result = cli.handle_show_command(mock_presets, args)

    assert result == 0
    # Verify JSON was printed
    call_arg = mock_console_print.call_args[0][0]
    # Should be valid JSON string
    parsed = json.loads(call_arg)
    assert parsed["name"] == "default"


def test_handle_show_command_not_found(mock_presets: MagicMock, mock_console_print: MagicMock) -> None:
    """Test the show command with non-existent preset."""
    args = argparse.Namespace(preset_name="nonexistent", type=None, json=False, flatten=False)

    # Ensure get_preset_by_name returns None for all preset types
    mock_presets.get_preset_by_name.return_value = None

    result = cli.handle_show_command(mock_presets, args)

    assert result == 1
    mock_console_print.assert_called_once()
    # Check error message contains preset name
    error_msg = mock_console_print.call_args[0][0]
    assert "nonexistent" in str(error_msg)
    assert "Error" in str(error_msg)


def test_handle_related_command(mock_presets: MagicMock, mock_console_print: MagicMock) -> None:
    """Test the related command."""
    args = argparse.Namespace(configure_preset="default", type="all", show_hidden=False, plain=False)

    result = cli.handle_related_command(mock_presets, args)

    assert result == 0
    mock_console_print.assert_called()

    # Test with specific type
    mock_console_print.reset_mock()
    args = argparse.Namespace(configure_preset="default", type="build", show_hidden=False, plain=False)

    result = cli.handle_related_command(mock_presets, args)

    assert result == 0
    mock_console_print.assert_called()


def test_handle_related_command_plain_output(mock_presets: MagicMock) -> None:
    """Test the related command with plain output for scripts."""
    args = argparse.Namespace(configure_preset="default", type="all", show_hidden=False, plain=True)

    with patch("builtins.print") as mock_print:
        result = cli.handle_related_command(mock_presets, args)

        assert result == 0
        mock_print.assert_called_once()
        # Should print available types
        assert "build test" in mock_print.call_args[0][0] or "test build" in mock_print.call_args[0][0]


def test_handle_related_command_not_found(mock_presets: MagicMock, mock_console_print: MagicMock) -> None:
    """Test the related command with non-existent configure preset."""
    args = argparse.Namespace(configure_preset="nonexistent", type="all", show_hidden=False, plain=False)

    # Ensure get_preset_by_name returns None
    mock_presets.get_preset_by_name.return_value = None

    result = cli.handle_related_command(mock_presets, args)

    assert result == 1
    mock_console_print.assert_called_once()
    # Check error message contains preset name
    error_msg = mock_console_print.call_args[0][0]
    assert "nonexistent" in str(error_msg)


def test_main_with_list_command() -> None:
    """Test the main function with list command."""
    test_args = ["cmakepresets", "--directory", "/some/dir", "list"]

    with patch("sys.argv", test_args):
        with patch("cmakepresets.cli.CMakePresets") as mock_preset_class:
            mock_instance = MagicMock()
            mock_preset_class.return_value = mock_instance

            with patch("cmakepresets.cli.handle_list_command") as mock_handler:
                mock_handler.return_value = 0

                result = cli.main()

                assert result == 0
                mock_handler.assert_called_once()
                mock_preset_class.assert_called_once_with("/some/dir")


def test_main_error_handling() -> None:
    """Test main function error handling."""
    test_args = ["cmakepresets", "--directory", "/some/dir", "list"]

    with patch("sys.argv", test_args):
        with patch("cmakepresets.cli.CMakePresets", side_effect=Exception("Test error")):
            with patch("cmakepresets.cli.console.print") as mock_print:
                result = cli.main()

                assert result == 1
                mock_print.assert_called_once()
                # Check error message
                error_msg = mock_print.call_args[0][0]
                assert "Error" in str(error_msg)
                assert "Test error" in str(error_msg)


# Integration tests with fake filesystem
@CMakePresets_json("""
{
    "version": 4,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "configurePresets": [
        {"name": "default", "generator": "Ninja"},
        {"name": "release", "generator": "Ninja", "cacheVariables": {"CMAKE_BUILD_TYPE": "Release"}}
    ],
    "buildPresets": [
        {"name": "default-build", "configurePreset": "default"},
        {"name": "release-build", "configurePreset": "release"}
    ],
    "testPresets": [
        {"name": "default-test", "configurePreset": "default"}
    ]
}
""")
def test_integration_list_command(mock_console_print: MagicMock) -> None:
    """Integration test for list command using real file system."""
    # Create CLI arguments
    args = argparse.Namespace(file="CMakePresets.json", directory=None, command="list", type="all", show_hidden=False, flat=True, verbose=0)

    with patch("sys.argv", ["cmakepresets", "--file", "CMakePresets.json", "list"]):
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            result = cli.main()

            assert result == 0
            mock_console_print.assert_called()

            # Check that all presets are in the output
            output_text = " ".join(str(call) for call in mock_console_print.call_args_list)
            assert "default" in output_text
            assert "release" in output_text


@CMakePresets_json("""
{
    "version": 4,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "configurePresets": [
        {"name": "base", "generator": "Ninja", "cacheVariables": {"VAR1": "base_value"}},
        {"name": "derived", "inherits": "base", "cacheVariables": {"VAR2": "derived_value"}}
    ]
}
""")
def test_integration_show_command(mock_console_print: MagicMock) -> None:
    """Integration test for show command using real file system."""
    # Create CLI arguments
    args = argparse.Namespace(
        file="CMakePresets.json", directory=None, command="show", preset_name="derived", type="configure", json=False, flatten=True, verbose=0
    )

    with patch("sys.argv", ["cmakepresets", "--file", "CMakePresets.json", "show", "derived"]):
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            # Instead use JSON output to verify content properly
            args.json = True
            result = cli.main()

            assert result == 0
            mock_console_print.assert_called()

            # With JSON output, we can verify the exact content
            json_output = mock_console_print.call_args_list[0][0][0]
            parsed = json.loads(json_output)
            assert parsed["name"] == "derived"
            assert "cacheVariables" in parsed
            assert "VAR1" in parsed["cacheVariables"]
            assert "VAR2" in parsed["cacheVariables"]
            assert parsed["cacheVariables"]["VAR1"] == "base_value"
            assert parsed["cacheVariables"]["VAR2"] == "derived_value"


@CMakePresets_json("""
{
    "version": 4,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "configurePresets": [
        {"name": "default", "generator": "Ninja"}
    ],
    "buildPresets": [
        {"name": "default-build", "configurePreset": "default"}
    ],
    "testPresets": [
        {"name": "default-test", "configurePreset": "default"}
    ]
}
""")
def test_integration_related_command(mock_console_print: MagicMock) -> None:
    """Integration test for related command using real file system."""
    # Create CLI arguments
    args = argparse.Namespace(
        file="CMakePresets.json", directory=None, command="related", configure_preset="default", type="all", show_hidden=False, plain=False, verbose=0
    )

    with patch("sys.argv", ["cmakepresets", "--file", "CMakePresets.json", "related", "default"]):
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            result = cli.main()

            assert result == 0
            mock_console_print.assert_called()

            # Check that related presets are in the output
            output_text = " ".join(str(call) for call in mock_console_print.call_args_list)
            assert "default-build" in output_text
            assert "default-test" in output_text
