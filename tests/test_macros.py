"""Tests for the macro resolution functionality."""

import os
import platform
from unittest.mock import patch

from cmakepresets.macros import MacroResolver, resolve_macros_in_preset, resolve_macros_in_string


def test_basic_macro_resolution() -> None:
    """Test resolving basic macros in a string."""
    resolver = MacroResolver("/path/to/source")
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


def test_environment_macros() -> None:
    """Test resolving environment-based macros."""
    with patch.dict(os.environ, {"PATH": "/usr/bin", "HOME": "/home/user"}):
        resolver = MacroResolver()

        # Create context with environment data
        preset = {"name": "env-test", "environment": {"CUSTOM_VAR": "custom-value"}}
        context = resolver._build_context(preset, "configure")

        # Test $env macro with system environment
        assert resolver.resolve_string("$env{PATH}", context) == "/usr/bin"

        # Test $env macro with preset environment
        assert resolver.resolve_string("$env{CUSTOM_VAR}", context) == "custom-value"

        # Test $penv macro (only parent environment)
        assert resolver.resolve_string("$penv{HOME}", context) == "/home/user"
        assert resolver.resolve_string("$penv{CUSTOM_VAR}", context) == ""  # Not in parent env

        # Test with non-existent environment variable
        assert resolver.resolve_string("$env{NONEXISTENT}", context) == ""
        assert resolver.resolve_string("$penv{NONEXISTENT}", context) == ""

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
    assert result.startswith(os.getcwd())
    assert result.endswith("$vendor{xide.buildDir}")


def test_resolve_in_preset() -> None:
    """Test resolving macros throughout a preset structure."""
    resolver = MacroResolver("/path/to/source")

    # Create a test preset with macros in various places
    preset = {
        "name": "test-preset",
        "generator": "Ninja",
        "binaryDir": "${sourceDir}/build/${presetName}",
        "cacheVariables": {"CMAKE_BUILD_TYPE": "Debug", "PROJECT_SOURCE_DIR": "${sourceDir}", "DOLLAR_SIGN": "${dollar}${dollar}"},
        "environment": {"PATH": "${sourceDir}/bin:$penv{PATH}", "NESTED": "${sourceDirName}/$env{PATH}"},
    }

    # Resolve macros in the preset
    resolved = resolver.resolve_in_preset(preset, "configure")

    # Check that the basic structure is preserved
    assert resolved["name"] == "test-preset"
    assert resolved["generator"] == "Ninja"

    # Check that macros are resolved
    assert resolved["binaryDir"] == "/path/to/source/build/test-preset"
    assert resolved["cacheVariables"]["PROJECT_SOURCE_DIR"] == "/path/to/source"
    assert resolved["cacheVariables"]["DOLLAR_SIGN"] == "$$"

    # Check environment variables with nested macros
    assert resolved["environment"]["PATH"].startswith("/path/to/source/bin:")
    assert resolved["environment"]["NESTED"].startswith("source/")


def test_convenience_functions() -> None:
    """Test the module-level convenience functions."""
    # Test string resolution
    context = {"name": "test", "value": 42}
    assert resolve_macros_in_string("${name} has value ${value}", context) == "test has value 42"

    # Test preset resolution
    preset = {"name": "quick-test", "binaryDir": "${sourceDir}/build"}
    resolved = resolve_macros_in_preset(preset, "configure", "/custom/source")
    assert resolved["binaryDir"] == "/custom/source/build"
