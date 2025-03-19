import argparse
import json
import os
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from rich.table import Table

from cmakepresets import cli
from cmakepresets.presets import CMakePresets

from .decorators import CMakePresets_json


@pytest.fixture(scope="function")  # type: ignore[misc]
def mock_console_print() -> Generator[MagicMock]:
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
        (p for p in getattr(presets, f"{preset_type}_presets") if p.get("name") == name),
        None,
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


@CMakePresets_json("""
{
    "version": 4,
    "cmakeMinimumRequired": {"major": 3, "minor": 28, "patch": 0},
    "configurePresets": [
        {"name": "default", "generator": "Ninja"},
        {"name": "debug", "generator": "Ninja"},
        {"name": "hidden-preset", "generator": "Ninja", "hidden": true}
    ],
    "buildPresets": [
        {"name": "default-build", "configurePreset": "default"},
        {"name": "debug-build", "configurePreset": "debug"}
    ],
    "testPresets": [
        {"name": "default-test", "configurePreset": "default"}
    ]
}
""")
def test_handle_list_command_flat(mock_console_print: MagicMock) -> None:
    """Test the list command with flat output."""
    args = argparse.Namespace(file="CMakePresets.json", directory=None, command="list", type="configure", show_hidden=False, flat=True, verbose=10)

    with patch("sys.argv", ["cmakepresets", "-vvvv", "list", "--type", "configure", "--flat"]):
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            result = cli.main()

            assert result == 0
            mock_console_print.assert_called()

            # Check output contains preset names
            output_text = " ".join(str(call) for call in mock_console_print.call_args_list)
            assert "default" in output_text
            assert "debug" in output_text
            assert "hidden-preset" not in output_text


@CMakePresets_json("""
{
    "version": 4,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "configurePresets": [
        {"name": "default", "generator": "Ninja"},
        {"name": "debug", "generator": "Ninja"}
    ],
    "buildPresets": [
        {"name": "default-build", "configurePreset": "default"},
        {"name": "debug-build", "configurePreset": "debug"}
    ],
    "testPresets": [
        {"name": "default-test", "configurePreset": "default"}
    ]
}
""")
def test_handle_list_command_tabular(mock_console_print: MagicMock) -> None:
    """Test the list command with tabular output."""
    args = argparse.Namespace(file="CMakePresets.json", directory=None, command="list", type="all", show_hidden=False, flat=False, verbose=0)

    with patch("sys.argv", ["cmakepresets", "list", "--type", "all"]):
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            result = cli.main()

            assert result == 0
            mock_console_print.assert_called()

            # First argument should be a table
            table_arg = mock_console_print.call_args[0][0]
            assert isinstance(table_arg, Table)


@CMakePresets_json("""
{
    "version": 4,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "configurePresets": [
        {"name": "default", "generator": "Ninja", "cacheVariables": {"CMAKE_BUILD_TYPE": "Debug"}}
    ]
}
""")
def test_handle_show_command(mock_console_print: MagicMock) -> None:
    """Test the show command."""
    # Test with standard output
    args = argparse.Namespace(
        file="CMakePresets.json",
        directory=None,
        command="show",
        preset_name="default",
        type="configure",
        json=False,
        flatten=False,
        resolve=False,
        verbose=0,
    )

    with patch("sys.argv", ["cmakepresets", "show", "default", "--type", "configure"]):
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            result = cli.main()

            assert result == 0
            mock_console_print.assert_called()

            # Reset for next test
            mock_console_print.reset_mock()

            # Test with JSON output
            args.json = True
            with patch("argparse.ArgumentParser.parse_args", return_value=args):
                result = cli.main()

                assert result == 0
                call_arg = mock_console_print.call_args[0][0]
                parsed = json.loads(call_arg)
                assert parsed["name"] == "default"
                assert parsed["generator"] == "Ninja"
                assert parsed["cacheVariables"]["CMAKE_BUILD_TYPE"] == "Debug"


@CMakePresets_json("""
{
    "version": 4,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "configurePresets": [
        {"name": "default", "generator": "Ninja"}
    ]
}
""")
def test_handle_show_command_not_found(mock_console_print: MagicMock) -> None:
    """Test the show command with non-existent preset."""
    args = argparse.Namespace(
        file="CMakePresets.json",
        directory=None,
        command="show",
        preset_name="nonexistent",
        type=None,
        json=False,
        flatten=False,
        resolve=False,
        verbose=0,
    )

    with patch("sys.argv", ["cmakepresets", "show", "nonexistent"]):
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            result = cli.main()

            assert result == 1
            mock_console_print.assert_called_once()
            # Check error message contains preset name
            error_msg = mock_console_print.call_args[0][0]
            assert "nonexistent" in str(error_msg)
            assert "Error" in str(error_msg)


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
def test_handle_related_command(mock_console_print: MagicMock) -> None:
    """Test the related command."""
    args = argparse.Namespace(
        file="CMakePresets.json",
        directory=None,
        command="related",
        configure_preset="default",
        type="all",
        show_hidden=False,
        plain=False,
        verbose=0,
    )

    with patch("sys.argv", ["cmakepresets", "related", "default", "--type", "all"]):
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            result = cli.main()

            assert result == 0
            mock_console_print.assert_called()

            # Check output contains related presets
            output_text = " ".join(str(call) for call in mock_console_print.call_args_list)
            assert "default-build" in output_text
            assert "default-test" in output_text

            # Reset for specific type test
            mock_console_print.reset_mock()

            # Test with specific type
            args.type = "build"
            with patch("sys.argv", ["cmakepresets", "related", "default", "--type", "build"]):
                with patch("argparse.ArgumentParser.parse_args", return_value=args):
                    result = cli.main()

                    assert result == 0
                    mock_console_print.assert_called()
                    output_text = " ".join(str(call) for call in mock_console_print.call_args_list)
                    assert "default-build" in output_text


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
def test_handle_related_command_plain_output(mock_console_print: MagicMock) -> None:
    """Test the related command with plain output for scripts."""
    args = argparse.Namespace(
        file="CMakePresets.json",
        directory=None,
        command="related",
        configure_preset="default",
        type="all",
        show_hidden=False,
        plain=True,
        verbose=0,
    )

    with patch("sys.argv", ["cmakepresets", "related", "default", "--plain"]):
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            with patch("builtins.print") as mock_print:
                result = cli.main()

                assert result == 0
                mock_print.assert_called_once()
                # Should print available types
                output = mock_print.call_args[0][0]
                assert "build" in output
                assert "test" in output


@CMakePresets_json("""
{
    "version": 4,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "configurePresets": [
        {"name": "default", "generator": "Ninja"}
    ]
}
""")
def test_handle_related_command_not_found(mock_console_print: MagicMock) -> None:
    """Test the related command with non-existent configure preset."""
    args = argparse.Namespace(
        file="CMakePresets.json",
        directory=None,
        command="related",
        configure_preset="nonexistent",
        type="all",
        show_hidden=False,
        plain=False,
        verbose=0,
    )

    with patch("sys.argv", ["cmakepresets", "related", "nonexistent"]):
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            result = cli.main()

            assert result == 1
            mock_console_print.assert_called_once()
            # Check error message contains preset name
            error_msg = mock_console_print.call_args[0][0]
            assert "nonexistent" in str(error_msg)


@CMakePresets_json("""
{
    "version": 4,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "configurePresets": [
        {"name": "default", "generator": "Ninja"}
    ]
}
""")
def test_main_with_list_command(mock_console_print: MagicMock) -> None:
    """Test the main function with list command."""
    args = argparse.Namespace(file="CMakePresets.json", directory=None, command="list", type="configure", show_hidden=False, flat=False, verbose=0)

    with patch("sys.argv", ["cmakepresets", "list"]):
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            result = cli.main()

            assert result == 0
            mock_console_print.assert_called()
            # Check output contains preset
            output_text = " ".join(str(call) for call in mock_console_print.call_args_list)
            assert "default" in output_text


@CMakePresets_json("""
{
    "version": 4,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "configurePresets": [
        {"name": "default", "generator": "Ninja"}
    ]
}
""")
def test_main_error_handling(mock_console_print: MagicMock) -> None:
    """Test main function error handling."""
    # Create a situation that would cause an exception
    args = argparse.Namespace(file="NonExistentFile.json", directory=None, command="list", type="configure", show_hidden=False, flat=False, verbose=0)

    with patch("sys.argv", ["cmakepresets", "--file", "NonExistentFile.json", "list"]):
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            result = cli.main()

            assert result == 1

            mock_console_print.assert_called()
            # Check error message
            error_msg = mock_console_print.call_args[0][0]
            assert "Error" in str(error_msg)


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
        file="CMakePresets.json",
        directory=None,
        command="show",
        preset_name="derived",
        type="configure",
        json=True,
        flatten=True,
        resolve=False,
        verbose=0,
    )

    with patch("sys.argv", ["cmakepresets", "--file", "CMakePresets.json", "show", "derived", "--json"]):
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            result = cli.main()

            assert result == 0
            mock_console_print.assert_called()

            # With JSON output, we can verify the exact content
            json_output = mock_console_print.call_args[0][0]
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
        file="CMakePresets.json",
        directory=None,
        command="related",
        configure_preset="default",
        type="all",
        show_hidden=False,
        plain=False,
        verbose=0,
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


@CMakePresets_json("""
{
    "version": 6,
    "cmakeMinimumRequired": {"major": 3, "minor": 29, "patch": 0},
    "configurePresets": [
        {
            "name": "macro-test",
            "generator": "Ninja",
            "binaryDir": "${sourceDir}/build/${presetName}",
            "cacheVariables": {
                "CMAKE_BUILD_TYPE": "Debug",
                "SOURCE_DIR": "${sourceDir}"
            }
        }
    ]
}
""")
def test_handle_show_command_with_resolve(mock_console_print: MagicMock) -> None:
    """Test the show command with macro resolution."""
    # Test with resolve option
    args = argparse.Namespace(
        file="CMakePresets.json",
        directory=None,
        command="show",
        preset_name="macro-test",
        type=None,
        json=True,
        flatten=False,
        resolve=True,
        verbose=0,
    )

    with patch("sys.argv", ["cmakepresets", "show", "macro-test", "--resolve", "--json"]):
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            result = cli.main()

            # Should succeed
            assert result == 0
            mock_console_print.assert_called_once()

            # Parse the output JSON to check resolved values
            json_output = mock_console_print.call_args[0][0]
            parsed = json.loads(json_output)

            # The source directory in tests will be the current directory
            source_dir = os.getcwd()

            # Check that macros were resolved
            assert parsed["binaryDir"] == f"{source_dir}/build/macro-test"
            assert parsed["cacheVariables"]["SOURCE_DIR"] == source_dir
