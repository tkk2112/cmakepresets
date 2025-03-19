import os
import platform

import pytest
from pyfakefs.fake_filesystem_unittest import Patcher

from cmakepresets.presets import CMakePresets

from .decorators import CMakePresets_json


@CMakePresets_json('{"version": 4, "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0}}')
def test_initialize_with_file_path() -> None:
    """Test initialization with a file path."""
    presets = CMakePresets("CMakePresets.json")
    assert isinstance(presets, CMakePresets)


@CMakePresets_json('{"version": 4, "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0}}')
def test_initialize_with_directory_path() -> None:
    """Test initialization with a directory path."""
    # With pyfakefs, the current directory contains our preset file
    presets = CMakePresets(".")
    assert isinstance(presets, CMakePresets)


def test_initialize_missing_file() -> None:
    """Test initialization with a missing file raises FileNotFoundError."""
    with Patcher():
        with pytest.raises(FileNotFoundError):
            CMakePresets("non_existent_file.json")


@CMakePresets_json("""
{
    "version": 4,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "configurePresets": [
        {"name": "default", "generator": "Ninja"},
        {"name": "debug", "generator": "Ninja", "binaryDir": "${sourceDir}/build/debug"}
    ]
}
""")
def test_get_configure_presets() -> None:
    """Test retrieving configure presets."""
    presets = CMakePresets("CMakePresets.json")
    configure_presets = presets.get_configure_presets()
    assert len(configure_presets) == 2
    assert configure_presets[0]["name"] == "default"
    assert configure_presets[1]["name"] == "debug"

    # Test the property accessor too
    assert presets.configure_presets == configure_presets


@CMakePresets_json("""
{
    "version": 4,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "buildPresets": [
        {"name": "release-build", "configurePreset": "release"},
        {"name": "debug-build", "configurePreset": "debug"}
    ]
}
""")
def test_get_build_presets() -> None:
    """Test retrieving build presets."""
    presets = CMakePresets("CMakePresets.json")
    build_presets = presets.get_build_presets()
    assert len(build_presets) == 2
    assert build_presets[0]["name"] == "release-build"
    assert build_presets[1]["name"] == "debug-build"

    # Test the property accessor too
    assert presets.build_presets == build_presets


@CMakePresets_json("""
{
    "version": 4,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "testPresets": [
        {"name": "unit-tests", "configurePreset": "debug"},
        {"name": "integration-tests", "configurePreset": "release"}
    ]
}
""")
def test_get_test_presets() -> None:
    """Test retrieving test presets."""
    presets = CMakePresets("CMakePresets.json")
    test_presets = presets.get_test_presets()
    assert len(test_presets) == 2
    assert test_presets[0]["name"] == "unit-tests"
    assert test_presets[1]["name"] == "integration-tests"

    # Test the property accessor too
    assert presets.test_presets == test_presets


@CMakePresets_json("""
{
    "version": 6,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "packagePresets": [
        {"name": "deb-package", "configurePreset": "release"},
        {"name": "rpm-package", "configurePreset": "release"}
    ]
}
""")
def test_get_package_presets() -> None:
    """Test retrieving package presets."""
    presets = CMakePresets("CMakePresets.json")
    package_presets = presets.get_package_presets()
    assert len(package_presets) == 2
    assert package_presets[0]["name"] == "deb-package"
    assert package_presets[1]["name"] == "rpm-package"

    # Test the property accessor too
    assert presets.package_presets == package_presets


@CMakePresets_json("""
{
    "version": 6,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "workflowPresets": [
        {"name": "ci-workflow", "steps": [{"type": "configure", "name": "default"}]},
        {"name": "release-workflow", "steps": [{"type": "configure", "name": "release"}]}
    ]
}
""")
def test_get_workflow_presets() -> None:
    """Test retrieving workflow presets."""
    presets = CMakePresets("CMakePresets.json")
    workflow_presets = presets.get_workflow_presets()
    assert len(workflow_presets) == 2
    assert workflow_presets[0]["name"] == "ci-workflow"
    assert workflow_presets[1]["name"] == "release-workflow"

    # Test the property accessor too
    assert presets.workflow_presets == workflow_presets


@CMakePresets_json("""
{
    "version": 4,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "configurePresets": [{"name": "default", "generator": "Ninja"}],
    "buildPresets": [{"name": "release-build", "configurePreset": "release"}],
    "testPresets": [{"name": "unit-tests", "configurePreset": "debug"}]
}
""")
def test_get_preset_by_name() -> None:
    """Test getting a preset by its specific type and name."""
    presets = CMakePresets("CMakePresets.json")

    # Find existing preset
    configure_preset = presets.get_preset_by_name("configure", "default")
    assert configure_preset is not None
    assert configure_preset["name"] == "default"

    # Find non-existent preset
    nonexistent = presets.get_preset_by_name("build", "nonexistent")
    assert nonexistent is None


@CMakePresets_json("""
{
    "version": 4,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "configurePresets": [{"name": "default", "generator": "Ninja"}],
    "buildPresets": [{"name": "release-build", "configurePreset": "release"}],
    "testPresets": [{"name": "unit-tests", "configurePreset": "debug"}]
}
""")
def test_find_preset() -> None:
    """Test finding a preset by name across all preset types."""
    presets = CMakePresets("CMakePresets.json")

    # Find preset in configurePresets
    default_preset = presets.find_preset("default")
    assert default_preset is not None
    assert default_preset["name"] == "default"

    # Find preset in testPresets
    test_preset = presets.find_preset("unit-tests")
    assert test_preset is not None
    assert test_preset["name"] == "unit-tests"

    # Try to find non-existent preset
    nonexistent = presets.find_preset("nonexistent")
    assert nonexistent is None


@CMakePresets_json(
    {
        "CMakePresets.json": """
    {
        "version": 4,
        "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
        "configurePresets": [{"name": "base", "generator": "Ninja"}],
        "include": ["nested/more_presets.json"]
    }
    """,
        "nested/more_presets.json": """
    {
        "version": 4,
        "configurePresets": [{"name": "nested", "generator": "Ninja"}],
        "buildPresets": [{"name": "nested-build", "configurePreset": "nested"}]
    }
    """,
    },
)
def test_presets_with_includes() -> None:
    """Test that presets from included files are also retrieved."""
    presets = CMakePresets("CMakePresets.json")

    # Should have presets from both files
    configure_presets = presets.get_configure_presets()
    assert len(configure_presets) == 2
    assert any(preset["name"] == "base" for preset in configure_presets)
    assert any(preset["name"] == "nested" for preset in configure_presets)

    # Should have build presets from the included file
    build_presets = presets.get_build_presets()
    assert len(build_presets) == 1
    assert build_presets[0]["name"] == "nested-build"


@CMakePresets_json(
    {
        "CMakePresets.json": """
    {
        "version": 4,
        "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
        "configurePresets": [{"name": "base", "generator": "Ninja"}]
    }
    """,
        "CMakeUserPresets.json": """
    {
        "version": 4,
        "configurePresets": [{"name": "user", "generator": "Ninja"}]
    }
    """,
    },
)
def test_user_presets_are_included() -> None:
    """Test that CMakeUserPresets.json is automatically included."""
    presets = CMakePresets("CMakePresets.json")

    # Should have presets from both files
    configure_presets = presets.get_configure_presets()
    assert len(configure_presets) == 2
    assert any(preset["name"] == "base" for preset in configure_presets)
    assert any(preset["name"] == "user" for preset in configure_presets)


@CMakePresets_json("""
{
    "version": 4,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "configurePresets": [
        {"name": "base", "generator": "Ninja", "cacheVariables": {"VAR1": "base_value"}},
        {"name": "debug", "inherits": "base", "cacheVariables": {"VAR2": "debug_value"}}
    ],
    "buildPresets": [
        {"name": "base-build", "configurePreset": "base"},
        {"name": "debug-build", "configurePreset": "debug"}
    ],
    "testPresets": [
        {"name": "base-test", "configurePreset": "base"},
        {"name": "debug-test", "configurePreset": "debug"}
    ]
}
""")
def test_get_preset_inheritance_chain() -> None:
    """Test retrieving the inheritance chain for a preset."""
    presets = CMakePresets("CMakePresets.json")

    # Test inheritance chain for debug preset which inherits from base
    chain = presets.get_preset_inheritance_chain("configure", "debug")
    assert len(chain) == 1
    assert chain[0]["name"] == "base"

    # Test preset with no inheritance
    chain = presets.get_preset_inheritance_chain("configure", "base")
    assert len(chain) == 0


@CMakePresets_json("""
{
    "version": 4,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "configurePresets": [
        {"name": "base", "generator": "Ninja", "cacheVariables": {"VAR1": "base_value"}},
        {"name": "debug", "inherits": "base", "cacheVariables": {"VAR2": "debug_value", "VAR1": "overridden_value"}},
        {"name": "extended", "inherits": "debug", "cacheVariables": {"VAR3": "extended_value"}}
    ]
}
""")
def test_flatten_preset() -> None:
    """Test flattening a preset with inheritance."""
    presets = CMakePresets("CMakePresets.json")

    # Test flattening a preset with multiple levels of inheritance
    flattened = presets.flatten_preset("configure", "extended")
    assert flattened["name"] == "extended"
    assert flattened["generator"] == "Ninja"
    # Should use overridden value
    assert flattened["cacheVariables"]["VAR1"] == "overridden_value"
    assert flattened["cacheVariables"]["VAR2"] == "debug_value"
    assert flattened["cacheVariables"]["VAR3"] == "extended_value"

    # Ensure inherits is not in the flattened preset
    assert "inherits" not in flattened


@CMakePresets_json("""
{
    "version": 4,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "configurePresets": [
        {"name": "base", "generator": "Ninja"},
        {"name": "debug", "generator": "Ninja"}
    ],
    "buildPresets": [
        {"name": "base-build", "configurePreset": "base"},
        {"name": "debug-build", "configurePreset": "debug"}
    ],
    "testPresets": [
        {"name": "base-test", "configurePreset": "base"},
        {"name": "debug-test", "configurePreset": "debug"}
    ]
}
""")
def test_get_dependent_presets() -> None:
    """Test getting presets dependent on a specific preset."""
    presets = CMakePresets("CMakePresets.json")

    dependents = presets.get_dependent_presets("configure", "base")
    assert len(dependents["buildPresets"]) == 1
    assert dependents["buildPresets"][0]["name"] == "base-build"
    assert len(dependents["testPresets"]) == 1
    assert dependents["testPresets"][0]["name"] == "base-test"


@CMakePresets_json("""
{
    "version": 4,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "configurePresets": [
        {"name": "base", "generator": "Ninja"}
    ],
    "buildPresets": [
        {"name": "direct-build", "configurePreset": "base"},
        {"name": "parent-build", "configurePreset": "base"},
        {"name": "inherited-build", "inherits": "parent-build"}
    ],
    "testPresets": [
        {"name": "direct-test", "configurePreset": "base"},
        {"name": "parent-test", "configurePreset": "base"},
        {"name": "inherited-test", "inherits": "parent-test"}
    ]
}
""")
def test_get_dependent_presets_with_inheritance() -> None:
    """Test getting presets dependent on a configure preset through inheritance."""
    presets = CMakePresets("CMakePresets.json")

    dependents = presets.get_dependent_presets("configure", "base")

    # Check build presets
    assert len(dependents["buildPresets"]) == 3
    build_names = [preset["name"] for preset in dependents["buildPresets"]]
    assert "direct-build" in build_names
    assert "parent-build" in build_names
    assert "inherited-build" in build_names

    # Check test presets
    assert len(dependents["testPresets"]) == 3
    test_names = [preset["name"] for preset in dependents["testPresets"]]
    assert "direct-test" in test_names
    assert "parent-test" in test_names
    assert "inherited-test" in test_names


@CMakePresets_json("""
{
    "version": 4,
    "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
    "configurePresets": [
        {"name": "base", "generator": "Ninja", "cacheVariables": {"VAR1": "base_value"}, "hidden": true},
        {"name": "debug", "inherits": "base", "cacheVariables": {"VAR2": "debug_value", "VAR1": "overridden_value"}},
        {"name": "extended", "inherits": "debug", "cacheVariables": {"VAR3": "extended_value"}, "hidden": true}
    ]
}
""")
def test_hidden_not_inherited_when_flattening() -> None:
    """Test that hidden property is not inherited when flattening presets."""
    presets = CMakePresets("CMakePresets.json")

    # Base preset is marked as hidden
    base = presets.get_preset_by_name("configure", "base")
    assert base is not None  # Make sure base is not None before indexing
    assert base["hidden"] is True

    # Debug preset inherits from base but should not inherit hidden property
    flattened_debug = presets.flatten_preset("configure", "debug")
    assert "hidden" not in flattened_debug

    # Extended preset explicitly sets hidden=true
    flattened_extended = presets.flatten_preset("configure", "extended")
    assert flattened_extended["hidden"] is True

    # Check that non-hidden properties are still inherited properly
    assert flattened_debug["generator"] == "Ninja"
    assert flattened_debug["cacheVariables"]["VAR1"] == "overridden_value"
    assert flattened_debug["cacheVariables"]["VAR2"] == "debug_value"
    assert flattened_extended["cacheVariables"]["VAR3"] == "extended_value"


@CMakePresets_json("""
{
    "version": 6,
    "cmakeMinimumRequired": {"major": 3, "minor": 28, "patch": 0},
    "configurePresets": [
        {"name": "base", "generator": "Ninja"},
        {"name": "debug", "generator": "Ninja"},
        {"name": "empty", "generator": "Ninja"}
    ],
    "buildPresets": [
        {"name": "base-build", "configurePreset": "base"},
        {"name": "debug-build", "configurePreset": "debug"},
        {"name": "another-build", "configurePreset": "base"}
    ],
    "testPresets": [
        {"name": "base-test", "configurePreset": "base"},
        {"name": "debug-test", "configurePreset": "debug"}
    ],
    "packagePresets": [
        {"name": "base-package", "configurePreset": "base"},
        {"name": "hidden-package", "configurePreset": "base", "hidden": true}
    ]
}
""")
def test_find_related_presets() -> None:
    """Test finding presets related to a specific configure preset."""
    presets = CMakePresets("CMakePresets.json")

    # Test finding all related presets
    related = presets.find_related_presets("base")
    assert related is not None
    assert len(related["build"]) == 2
    assert len(related["test"]) == 1
    assert len(related["package"]) == 2

    # Test finding only build presets
    build_related = presets.find_related_presets("base", "build")
    assert build_related is not None
    assert "build" in build_related
    assert len(build_related["build"]) == 2
    assert list(build_related.keys()) == ["build"]

    # Test finding related presets for a preset with no dependents
    empty_related = presets.find_related_presets("empty")
    assert empty_related is not None
    assert len(empty_related["build"]) == 0
    assert len(empty_related["test"]) == 0
    assert len(empty_related["package"]) == 0

    # Test nonexistent preset
    nonexistent_related = presets.find_related_presets("nonexistent")
    assert nonexistent_related is None


@CMakePresets_json("""
{
    "version": 6,
    "cmakeMinimumRequired": {"major": 3, "minor": 29, "patch": 0},
    "configurePresets": [
        {
            "name": "with-macros",
            "generator": "Ninja",
            "binaryDir": "${sourceDir}/build/${presetName}",
            "cacheVariables": {
                "CMAKE_BUILD_TYPE": "Debug",
                "PROJECT_SOURCE_DIR": "${sourceDir}",
                "SOURCE_PARENT": "${sourceParentDir}",
                "SOURCE_NAME": "${sourceDirName}",
                "PRESET_NAME": "${presetName}",
                "PATH_SEP": "${pathListSep}",
                "DOLLAR_SIGN": "${dollar}",
                "SYSTEM_NAME": "${hostSystemName}",
                "ENV_PATH": "$env{PATH}",
                "PENV_HOME": "$penv{HOME}"
            }
        }
    ]
}
""")
def test_resolve_macro_values() -> None:
    """Test resolving macros in a preset."""
    presets = CMakePresets("CMakePresets.json")

    # Get the preset with macros resolved
    resolved = presets.resolve_macro_values("configure", "with-macros")

    # Verify the basic preset properties were preserved
    assert resolved["name"] == "with-macros"
    assert resolved["generator"] == "Ninja"

    # Verify the macros were resolved
    source_dir = os.getcwd()  # In the test environment
    assert resolved["binaryDir"] == f"{source_dir}/build/with-macros"

    # Check cache variables
    cache_vars = resolved["cacheVariables"]
    assert cache_vars["PROJECT_SOURCE_DIR"] == source_dir
    assert cache_vars["SOURCE_PARENT"] == os.path.dirname(source_dir)
    assert cache_vars["SOURCE_NAME"] == os.path.basename(source_dir)
    assert cache_vars["PRESET_NAME"] == "with-macros"
    assert cache_vars["PATH_SEP"] == os.pathsep
    assert cache_vars["DOLLAR_SIGN"] == "$"
    assert cache_vars["SYSTEM_NAME"] == platform.system()

    # Environment variables will depend on the test environment
    assert "ENV_PATH" in cache_vars
    assert "PENV_HOME" in cache_vars


@CMakePresets_json("""
{
    "version": 6,
    "cmakeMinimumRequired": {"major": 3, "minor": 29, "patch": 0},
    "configurePresets": [
        {
            "name": "with-nested-macros",
            "generator": "Ninja",
            "binaryDir": "${sourceDir}/build/${presetName}",
            "environment": {
                "CUSTOM_VAR": "custom-value",
                "NESTED_VAR": "${sourceDir}/$env{CUSTOM_VAR}"
            }
        }
    ]
}
""")
def test_resolve_nested_macro_values() -> None:
    """Test resolving nested macros in a preset."""
    presets = CMakePresets("CMakePresets.json")

    # Get the preset with macros resolved
    resolved = presets.resolve_macro_values("configure", "with-nested-macros")

    # Verify nested macros in environment are resolved
    source_dir = os.getcwd()  # In the test environment
    assert resolved["environment"]["NESTED_VAR"] == f"{source_dir}/custom-value"


@CMakePresets_json("""
{
    "version": 6,
    "cmakeMinimumRequired": {"major": 3, "minor": 29, "patch": 0},
    "configurePresets": [
        {
            "name": "with-vendor-macros",
            "generator": "Ninja",
            "binaryDir": "$vendor{xide.buildDir}",
            "cacheVariables": {
                "VENDOR_VAR": "$vendor{xide.customValue}"
            }
        }
    ]
}
""")
def test_resolve_vendor_macro_values() -> None:
    """Test handling vendor macros in a preset."""
    presets = CMakePresets("CMakePresets.json")

    # Get the preset with macros resolved
    resolved = presets.resolve_macro_values("configure", "with-vendor-macros")

    # Verify vendor macros are left as-is
    assert resolved["binaryDir"] == "$vendor{xide.buildDir}"
    assert resolved["cacheVariables"]["VENDOR_VAR"] == "$vendor{xide.customValue}"
