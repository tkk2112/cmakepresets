import os
import platform
from pathlib import Path
from unittest.mock import patch

from cmakepresets.constants import TEST
from cmakepresets.macros import MacroResolver, resolve_macros_in_preset, resolve_macros_in_string
from cmakepresets.paths import CMakeRoot


def test_basic_macro_resolution() -> None:
    """Test resolving basic macros in a string."""
    # Create resolver with specific path to get predictable source dir
    root = CMakeRoot("/path/to/source/CMakePresets.json")
    resolver = MacroResolver(root)
    context = resolver._create_basic_context({"name": "test-preset"})

    # Test source directory macros
    assert resolver.resolve_string("${sourceDir}", context) == "/path/to/source"
    assert resolver.resolve_string("${sourceParentDir}", context) == "/path/to"
    assert resolver.resolve_string("${sourceDirName}", context) == "source"

    # Test preset name macro
    assert resolver.resolve_string("${presetName}", context) == "test-preset"

    # Test system macros
    assert resolver.resolve_string("${hostSystemName}", context) == platform.system()
    assert resolver.resolve_string("${pathListSep}", context) == os.pathsep

    # Test dollar macro
    assert resolver.resolve_string("${dollar}", context) == "$"

    # Test with multiple macros in a string
    result = resolver.resolve_string("${sourceDir}/build/${presetName}", context)
    assert result == "/path/to/source/build/test-preset"


def test_file_based_macro_resolution() -> None:
    """Test resolving macros relative to a CMakePresets.json file."""
    # Create resolver with a path to CMakePresets.json (using second positional arg)
    root = CMakeRoot("/path/to/project/CMakePresets.json")
    resolver = MacroResolver(root)
    context = resolver._create_basic_context({"name": "test-preset"})

    # Source directory should be the directory containing CMakePresets.json
    assert resolver.resolve_string("${sourceDir}", context) == "/path/to/project"
    assert resolver.resolve_string("${sourceParentDir}", context) == "/path/to"
    assert resolver.resolve_string("${sourceDirName}", context) == "project"

    result = resolver.resolve_string("${sourceDir}/build/${presetName}", context)
    assert result == "/path/to/project/build/test-preset"


def test_environment_macros() -> None:
    """Test resolving environment-based macros."""
    with patch.dict(os.environ, {"PATH": "/usr/bin", "HOME": "/home/user"}):
        root = CMakeRoot("/projects/my-project/CMakePresets.json")
        resolver = MacroResolver(root)

        # Create context with environment data
        preset = {"name": "env-test", "environment": {"CUSTOM_VAR": "custom-value"}}
        context = resolver._build_context(preset)

        # Test $env macro with system environment
        assert resolver.resolve_string("$env{PATH}", context) == "/usr/bin"

        # Test $env macro with preset environment
        assert resolver.resolve_string("$env{CUSTOM_VAR}", context) == "custom-value"

        # Test $penv macro (only parent environment)
        assert resolver.resolve_string("$penv{HOME}", context) == "/home/user"
        assert resolver.resolve_string("$penv{CUSTOM_VAR}", context) == "$penv{CUSTOM_VAR}"  # Not in parent env

        # Test with non-existent environment variable
        assert resolver.resolve_string("$env{NONEXISTENT}", context) == "$env{NONEXISTENT}"
        assert resolver.resolve_string("$penv{NONEXISTENT}", context) == "$penv{NONEXISTENT}"

        # Test mixed environment and standard macros
        result = resolver.resolve_string("${sourceDir}/$env{CUSTOM_VAR}", context)
        assert result.endswith("/custom-value")


def test_vendor_macros() -> None:
    """Test handling of vendor macros."""
    resolver = MacroResolver()
    context = resolver._create_basic_context({"name": "vendor-test"})

    # Vendor macros should be left as-is
    assert resolver.resolve_string("$vendor{xide.buildDir}", context) == "$vendor{xide.buildDir}"

    # Mixed with resolvable macros
    result = resolver.resolve_string("${sourceDir}/$vendor{xide.buildDir}", context)
    assert result.startswith(str(Path.cwd()))
    assert result.endswith("$vendor{xide.buildDir}")


def test_resolve_in_preset() -> None:
    """Test resolving macros throughout a preset structure."""
    with patch.dict(os.environ, {"PATH": "/usr/bin", "HOME": "/home/user"}):
        resolver = MacroResolver(CMakeRoot("/path/to/source"))

        # Create a test preset with macros in various places
        preset = {
            "name": "test-preset",
            "generator": "Ninja",
            "binaryDir": "${sourceDir}/build/${presetName}",
            "cacheVariables": {"CMAKE_BUILD_TYPE": "Debug", "PROJECT_SOURCE_DIR": "${sourceDir}", "DOLLAR_SIGN": "${dollar}${dollar}"},
            "environment": {"PATH": "${sourceDir}/bin:$penv{PATH}", "NESTED": "${sourceDirName}/$env{PATH}"},
        }

        # Resolve macros in the preset
        resolved = resolver.resolve_in_preset(preset)

        # Check that the basic structure is preserved
        assert resolved["name"] == "test-preset"
        assert resolved["generator"] == "Ninja"

        # Check that macros are resolved
        assert resolved["binaryDir"] == "/path/to/source/build/test-preset"
        assert resolved["cacheVariables"]["PROJECT_SOURCE_DIR"] == "/path/to/source"
        assert resolved["cacheVariables"]["DOLLAR_SIGN"] == "$$"

        # Check environment with nested macros
        assert resolved["environment"]["PATH"] == "/path/to/source/bin:/usr/bin"
        assert resolved["environment"]["NESTED"] == "source//path/to/source/bin:/usr/bin"


def test_convenience_functions() -> None:
    """Test the module-level convenience functions."""
    # Test string resolution
    context = {"name": TEST, "value": 42}
    assert resolve_macros_in_string("${name} has value ${value}", context) == "test has value 42"

    # Test preset resolution with positional source_dir
    preset = {"name": "quick-test", "binaryDir": "${sourceDir}/build"}
    resolved = resolve_macros_in_preset(preset, "/custom/source")
    assert resolved["binaryDir"] == "/custom/source/build"

    # Test preset resolution with CMakePresets.json file
    preset = {"name": "file-test", "binaryDir": "${sourceDir}/build/${presetName}"}
    resolved = resolve_macros_in_preset(
        preset,
        "/some/path/CMakePresets.json",
    )
    assert resolved["binaryDir"] == "/some/path/build/file-test"


def test_resolve_macros_with_empty_values() -> None:
    """Test macro resolution with empty or None values."""
    resolver = MacroResolver()

    # Test with empty string
    assert resolver.resolve_string("", {}) == ""

    # Test with macros that don't exist in context
    result = resolver.resolve_string("${nonexistent}", {})
    assert result == "${nonexistent}"  # Should preserve unresolved macros

    # Test with None values in context
    context = {"test": None}
    result = resolver.resolve_string("${test}", context)
    assert result == "None"  # None should be converted to string


def test_host_system_name_override() -> None:
    """Test that CMAKE_HOST_SYSTEM_NAME in cacheVariables overrides hostSystemName."""
    resolver = MacroResolver()

    # Create a preset that uses hostSystemName but also overrides it in cacheVariables
    preset = {
        "name": "override-test",
        "generator": "Ninja",
        "cacheVariables": {
            "CMAKE_HOST_SYSTEM_NAME": "Override",
            "ORIGINAL_HOST": "${hostSystemName}",
        },
        "architecture": {
            "value": "${hostSystemName}",
            "strategy": "external",
        },
    }

    # Resolve macros in the preset
    resolved = resolver.resolve_in_preset(preset)

    # Original host system name should be preserved in the cache variable
    assert resolved["cacheVariables"]["ORIGINAL_HOST"] == platform.system()

    # But architecture value should use the override
    assert resolved["architecture"]["value"] == "Override"


def test_source_dir_override() -> None:
    """Test that CMAKE_SOURCE_DIR in cacheVariables can override sourceDir."""
    root = CMakeRoot("/original/source/dir/CMakePresets.json")
    resolver = MacroResolver(root)

    # Create a preset with CMAKE_SOURCE_DIR override
    preset = {
        "name": "source-override-test",
        "binaryDir": "${sourceDir}/build",
        "cacheVariables": {
            "CMAKE_SOURCE_DIR": "/custom/source/dir",
            "ORIGINAL_SOURCE_DIR": "${sourceDir}",
        },
    }

    # Resolve macros in the preset
    resolved = resolver.resolve_in_preset(preset)

    # Check that sourceDir is used from the resolver's source_dir initially
    assert resolved["cacheVariables"]["ORIGINAL_SOURCE_DIR"] == "/original/source/dir"

    # But binaryDir should now use the overridden source directory
    assert resolved["binaryDir"] == "/custom/source/dir/build"
