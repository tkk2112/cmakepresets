import os
import platform
from unittest.mock import patch

from cmakepresets.constants import CONFIGURE, TEST
from cmakepresets.macros import MacroResolver, resolve_macros_in_preset, resolve_macros_in_string


def test_basic_macro_resolution() -> None:
    """Test resolving basic macros in a string."""
    # Create resolver with specific path to get predictable source dir
    resolver = MacroResolver("/path/to/source/CMakePresets.json")
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
    resolver = MacroResolver("/path/to/project/CMakePresets.json")
    context = resolver._create_basic_context({"name": "test-preset"})

    # Source directory should be the directory containing CMakePresets.json
    assert resolver.resolve_string("${sourceDir}", context) == "/path/to/project"
    assert resolver.resolve_string("${sourceParentDir}", context) == "/path/to"
    assert resolver.resolve_string("${sourceDirName}", context) == "project"

    # Test with relative paths
    result = resolver.resolve_string("${sourceDir}/build/${presetName}", context)
    assert result == "/path/to/project/build/test-preset"


def test_environment_macros() -> None:
    """Test resolving environment-based macros."""
    with patch.dict(os.environ, {"PATH": "/usr/bin", "HOME": "/home/user"}):
        resolver = MacroResolver()

        # Create context with environment data
        preset = {"name": "env-test", "environment": {"CUSTOM_VAR": "custom-value"}}
        context = resolver._build_context(preset, CONFIGURE)

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
    resolved = resolver.resolve_in_preset(preset, CONFIGURE)

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
    context = {"name": TEST, "value": 42}
    assert resolve_macros_in_string("${name} has value ${value}", context) == "test has value 42"

    # Test preset resolution with positional source_dir
    preset = {"name": "quick-test", "binaryDir": "${sourceDir}/build"}
    resolved = resolve_macros_in_preset(preset, CONFIGURE, source_dir="/custom/source")
    assert resolved["binaryDir"] == "/custom/source/build"

    # Test preset resolution with CMakePresets.json file
    preset = {"name": "file-test", "binaryDir": "${sourceDir}/build/${presetName}"}
    resolved = resolve_macros_in_preset(
        preset,
        CONFIGURE,
        "",  # empty source_dir
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


def test_path_relativity() -> None:
    """Test that paths are handled correctly relative to CMakePresets.json."""
    # Create resolver with a specific CMakePresets.json location
    resolver = MacroResolver("/home/user/project/CMakePresets.json")

    # Create a test preset with relative and absolute paths
    preset = {
        "name": "path-test",
        "generator": "Ninja",
        "binaryDir": "build/${presetName}",  # Relative path
        "installDir": "/opt/install/${presetName}",  # Absolute path
        "cacheVariables": {
            "RELATIVE_PATH": "src/lib",
            "ABSOLUTE_PATH": "/usr/local/include",
        },
    }

    # Resolve macros in the preset
    resolved = resolver.resolve_in_preset(preset, CONFIGURE)

    # Check relative path handling (should be relative to CMakePresets.json location)
    assert resolved["binaryDir"] == "/home/user/project/build/path-test"
    assert resolved["cacheVariables"]["RELATIVE_PATH"] == "src/lib"  # Unchanged as no macros to resolve

    # Check absolute path handling (should remain absolute)
    assert resolved["installDir"] == "/opt/install/path-test"
    assert resolved["cacheVariables"]["ABSOLUTE_PATH"] == "/usr/local/include"  # Unchanged

    # Test with relative_paths=True
    resolved_relative = resolver.resolve_in_preset(preset, CONFIGURE, relative_paths=True)

    # Check that binaryDir is now relative to source directory
    assert resolved_relative["binaryDir"] == "build/path-test"


def test_relative_paths_with_convenience_function() -> None:
    """Test the relative_paths parameter in resolve_macros_in_preset."""
    preset = {
        "name": "rel-path-test",
        "binaryDir": "${sourceDir}/build/${presetName}",
    }

    # With relative_paths=False (default), should get absolute paths
    resolved_abs = resolve_macros_in_preset(
        preset,
        CONFIGURE,
        "",  # empty source_dir
        "/path/to/CMakePresets.json",
    )
    assert resolved_abs["binaryDir"] == "/path/to/build/rel-path-test"

    # With relative_paths=True, should get paths relative to source dir
    resolved_rel = resolve_macros_in_preset(
        preset,
        CONFIGURE,
        "",  # empty source_dir
        "/path/to/CMakePresets.json",
        True,  # relative_paths=True
    )
    assert resolved_rel["binaryDir"] == "build/rel-path-test"


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
    resolved = resolver.resolve_in_preset(preset, CONFIGURE)

    # Original host system name should be preserved in the cache variable
    assert resolved["cacheVariables"]["ORIGINAL_HOST"] == platform.system()

    # But architecture value should use the override
    assert resolved["architecture"]["value"] == "Override"


def test_source_dir_override() -> None:
    """Test that CMAKE_SOURCE_DIR in cacheVariables can override sourceDir."""
    resolver = MacroResolver("/original/source/dir/CMakePresets.json")

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
    resolved = resolver.resolve_in_preset(preset, CONFIGURE)

    # Check that sourceDir is used from the resolver's source_dir initially
    assert resolved["cacheVariables"]["ORIGINAL_SOURCE_DIR"] == "/original/source/dir"

    # But binaryDir should now use the overridden source directory
    assert resolved["binaryDir"] == "/custom/source/dir/build"


def test_complex_path_scenarios() -> None:
    """Test more complex path scenarios including nesting and combinations."""
    resolver = MacroResolver("/home/user/project/CMakePresets.json")

    # Create a preset with complex path scenarios
    preset = {
        "name": "complex-paths",
        "binaryDir": "${sourceDir}/../builds/${presetName}",  # Parent dir navigation
        "installDir": "${sourceDir}/inst/${presetName}",  # Normal relative
        "variables": {
            "NESTED_PATH": "${sourceDir}/src/${presetName}/lib",  # Nested path
            "PARENT_NESTED": "${sourceParentDir}/other/${sourceDirName}/build",  # Complex nesting
        },
    }

    # Normal resolution (absolute paths)
    resolved = resolver.resolve_in_preset(preset, CONFIGURE)
    assert resolved["binaryDir"] == "/home/user/builds/complex-paths"
    assert resolved["installDir"] == "/home/user/project/inst/complex-paths"
    assert resolved["variables"]["NESTED_PATH"] == "/home/user/project/src/complex-paths/lib"
    assert resolved["variables"]["PARENT_NESTED"] == "/home/user/other/project/build"

    # Relative path resolution
    resolved_rel = resolver.resolve_in_preset(preset, CONFIGURE, relative_paths=True)
    assert resolved_rel["binaryDir"] == "../builds/complex-paths"  # Should be relative to source dir
    assert resolved_rel["installDir"] == "inst/complex-paths"
    assert resolved_rel["variables"]["NESTED_PATH"] == "src/complex-paths/lib"
    assert resolved_rel["variables"]["PARENT_NESTED"] == "../other/project/build"


def test_multiple_path_fields() -> None:
    """Test that multiple path fields are properly handled."""
    resolver = MacroResolver("/home/user/project/CMakePresets.json")

    # Create a preset with multiple path fields
    preset = {
        "name": "multiple-paths",
        "binaryDir": "${sourceDir}/build",
        "installDir": "${sourceDir}/install",
        "cmakeExecutable": "${sourceDir}/bin/cmake",
        "variables": {
            "SOME_PATH": "${sourceDir}/lib",
            "OTHER_DIR": "${sourceDir}/include",
            "NON_PATH": "just-a-string",
        },
    }

    # Resolve with relative paths
    resolved = resolver.resolve_in_preset(preset, CONFIGURE, relative_paths=True)

    # All path fields should be relative
    assert resolved["binaryDir"] == "build"
    assert resolved["installDir"] == "install"
    assert resolved["cmakeExecutable"] == "bin/cmake"
    assert resolved["variables"]["SOME_PATH"] == "lib"
    assert resolved["variables"]["OTHER_DIR"] == "include"
    assert resolved["variables"]["NON_PATH"] == "just-a-string"  # Non-path field unchanged

    # Resolve with absolute paths
    resolved_abs = resolver.resolve_in_preset(preset, CONFIGURE, relative_paths=False)

    # All path fields should be absolute
    assert resolved_abs["binaryDir"] == "/home/user/project/build"
    assert resolved_abs["installDir"] == "/home/user/project/install"
    assert resolved_abs["cmakeExecutable"] == "/home/user/project/bin/cmake"
