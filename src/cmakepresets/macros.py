import copy
import os
import platform
import re
from typing import Any, cast

from . import logger as mainLogger

logger = mainLogger.getChild(__name__)


class MacroResolver:
    """Class for resolving macros in CMake preset values."""

    def __init__(self, presets_file_path: str = "", cmake_presets_file: str = ""):
        """
        Initialize the macro resolver.

        Args:
            presets_file_path: Path to the CMakePresets.json file. If provided,
                               its directory is used as the source directory.
            cmake_presets_file: Alternative way to specify the path
        """
        # Use cmake_presets_file if provided, otherwise use positional arg
        actual_path = cmake_presets_file or presets_file_path

        if actual_path:
            # If the path ends with '.json', treat it as a file and use its directory.
            if actual_path.endswith(".json"):
                self.source_dir = os.path.abspath(os.path.dirname(actual_path))
            else:
                self.source_dir = os.path.abspath(actual_path)
        else:
            self.source_dir = os.path.abspath(os.getcwd())

        # Store the presets file path for context
        self.presets_file_path = actual_path

    def _normalize_path(self, path: str) -> str:
        """
        Normalize a path to resolve any '..' and '.' components.

        Args:
            path: Path to normalize

        Returns:
            Normalized absolute path
        """
        return os.path.normpath(path)

    def resolve_in_preset(
        self,
        preset: dict[str, Any],
        preset_type: str,
        relative_paths: bool = False,
        extra_env: dict[str, str] | None = None,
        file_paths: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Resolve all macros in a preset.

        Args:
            preset: The preset dictionary
            preset_type: Type of preset (configure, build, test, etc.)
            relative_paths: If True, paths are made relative to the preset file directory
            extra_env: Optional environment variables to use for resolution
            file_paths: Dictionary mapping preset names to file paths

        Returns:
            A new preset with all macros resolved
        """
        # Deep copy the preset to avoid modifying the original
        resolved_preset = copy.deepcopy(preset)

        # Build initial context for macro resolution
        context = self._build_context(preset, preset_type, file_paths, extra_env)

        # Process cache variables first to allow for overrides
        context = self._process_cache_variables(resolved_preset, context)

        # Process the rest of the preset with the updated context
        self._process_remaining_values(resolved_preset, context)

        # Handle path normalization and relativity
        self._process_paths(resolved_preset, relative_paths)

        return resolved_preset

    def _process_cache_variables(self, preset: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Process cache variables and update the context with overrides."""
        if "cacheVariables" not in preset:
            return context

        # First pass: resolve cache variables to allow overrides
        resolved_cache_vars = {}
        for k, v in preset["cacheVariables"].items():
            resolved_cache_vars[k] = self._resolve_recursive(v, context)
        preset["cacheVariables"] = resolved_cache_vars

        # Update context with overrides from cache variables
        updated_context = dict(context)

        if "CMAKE_HOST_SYSTEM_NAME" in resolved_cache_vars:
            updated_context["hostSystemName"] = resolved_cache_vars["CMAKE_HOST_SYSTEM_NAME"]

        if "CMAKE_SOURCE_DIR" in resolved_cache_vars:
            source_dir_override = resolved_cache_vars["CMAKE_SOURCE_DIR"]
            if source_dir_override:
                updated_context["sourceDir"] = source_dir_override
                # Update related paths
                updated_context["sourceParentDir"] = os.path.dirname(source_dir_override)
                updated_context["sourceDirName"] = os.path.basename(source_dir_override)

        return updated_context

    def _process_remaining_values(self, preset: dict[str, Any], context: dict[str, Any]) -> None:
        """Process all remaining values in the preset using the updated context."""
        for key, value in list(preset.items()):
            if key != "cacheVariables":  # Skip cache variables as they were already resolved
                preset[key] = self._resolve_recursive(value, context)

    def _process_paths(self, preset: dict[str, Any], relative_paths: bool) -> None:
        """Process path fields to handle normalization and relative paths."""
        # Known path fields in presets
        path_fields = self._find_path_fields(preset)

        for field_path in path_fields:
            # Get the value using the field path
            value = self._get_nested_value(preset, field_path)
            if not isinstance(value, str):
                continue

            # Make absolute and normalize
            if not os.path.isabs(value):
                value = os.path.join(self.source_dir, value)
            value = self._normalize_path(value)

            # Update the value
            self._set_nested_value(preset, field_path, value)

            # Make relative if requested
            if relative_paths:
                try:
                    rel_path = os.path.relpath(value, self.source_dir)
                    self._set_nested_value(preset, field_path, rel_path)
                except (ValueError, OSError):
                    # If relpath fails, keep absolute
                    pass

    def _find_path_fields(self, preset: dict[str, Any]) -> list[tuple[str, ...]]:
        """Find fields in the preset that appear to be paths."""
        path_fields: list[tuple[str, ...]] = []

        # Common path fields in CMake presets
        known_path_fields = [
            ("binaryDir",),
            ("installDir",),
            ("cmakeExecutable",),
            ("sourceDir",),
        ]

        # Add fields that exist in the preset
        for field in known_path_fields:
            if self._has_nested_value(preset, field):
                path_fields.append(field)

        # Look for paths in nested structures like 'variables'
        if "variables" in preset and isinstance(preset["variables"], dict):
            for key, var in preset["variables"].items():
                if isinstance(var, str) and ("path" in key.lower() or "dir" in key.lower() or "directory" in key.lower() or "parent" in key.lower()):
                    path_fields.append(("variables", key))

        return path_fields

    def _has_nested_value(self, obj: dict[str, Any], path: tuple[str, ...]) -> bool:
        """Check if a nested value exists in the object."""
        current = obj
        for key in path:
            if not isinstance(current, dict) or key not in current:
                return False
            current = current[key]
        return True

    def _get_nested_value(self, obj: dict[str, Any], path: tuple[str, ...]) -> Any:
        """Get a nested value from an object using a path tuple."""
        current = obj
        for key in path:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]
        return current

    def _set_nested_value(self, obj: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
        """Set a nested value in an object using a path tuple."""
        current = obj
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[path[-1]] = value

    def _build_context(
        self,
        preset: dict[str, Any],
        preset_type: str,
        file_paths: dict[str, str] | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Build context information for macro resolution."""
        # Start with basic context
        context = self._create_basic_context(preset)

        # Add generator information if available
        if "generator" in preset:
            context["generator"] = preset["generator"]

        # Add file directory information if available
        preset_name = preset.get("name", "")
        if file_paths and preset_name and preset_name in file_paths:
            filepath = file_paths[preset_name]
            if filepath:
                context["fileDir"] = os.path.dirname(filepath)
        elif self.presets_file_path:
            if os.path.isdir(self.presets_file_path):
                context["fileDir"] = self.presets_file_path
            else:
                context["fileDir"] = os.path.dirname(self.presets_file_path)

        # Add environment information
        env_context = self._get_environment_context(preset, extra_env)
        context.update(env_context)

        return context

    def _create_basic_context(self, preset: dict[str, Any]) -> dict[str, Any]:
        """Create basic context with standard macros."""
        return {
            "sourceDir": self.source_dir,
            "sourceParentDir": os.path.dirname(self.source_dir),
            "sourceDirName": os.path.basename(self.source_dir),
            "presetName": preset.get("name", ""),
            "hostSystemName": platform.system(),
            "dollar": "$",
            "pathListSep": os.pathsep,
        }

    def _get_environment_context(
        self,
        preset: dict[str, Any],
        extra_env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Get environment information for the context."""
        # First from parent environment
        parent_env = dict(os.environ)

        # Then from preset environment, if any
        preset_env: dict[str, str] = {}
        if "environment" in preset:
            preset_env = cast(dict[str, str], preset.get("environment", {}))

        # Combine with any provided env dict
        if extra_env:
            # User-provided env takes precedence
            combined_env = {**preset_env, **extra_env}
        else:
            combined_env = preset_env

        # Final environment is parent env updated with combined env
        final_env = {**parent_env, **combined_env}

        return {
            "env": final_env,
            "penv": parent_env,
        }

    def _resolve_recursive(self, value: Any, context: dict[str, Any]) -> Any:
        """Recursively resolve macros in a value."""
        if isinstance(value, str):
            return self.resolve_string(value, context)
        elif isinstance(value, dict):
            for k, v in value.items():
                value[k] = self._resolve_recursive(v, context)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                value[i] = self._resolve_recursive(item, context)
        return value

    def resolve_string(self, value: str, context: dict[str, Any]) -> str:
        def replace_macro(match: re.Match[str]) -> str:
            macro_name: str = match.group(1)
            return str(context.get(macro_name, match.group(0)))

        def replace_env(match: re.Match[str]) -> str | Any:
            env_name: str = match.group(1)
            return context.get("env", {}).get(env_name, "")

        def replace_penv(match: re.Match[str]) -> str | Any:
            env_name: str = match.group(1)
            return context.get("penv", {}).get(env_name, "")

        result = re.sub(r"\${([^}]+)}", replace_macro, value)
        result = re.sub(r"\$env{([^}]+)}", replace_env, result)
        result = re.sub(r"\$penv{([^}]+)}", replace_penv, result)
        if re.search(r"\$vendor{([^}]+)}", result):
            vendor_macros = re.findall(r"\$vendor{([^}]+)}", result)
            logger.warning(f"String contains vendor macros which cannot be resolved: {vendor_macros}")
        return result


def create_resolver(source_dir: str = "", cmake_presets_file: str = "") -> MacroResolver:
    """
    Create a new MacroResolver instance.

    Args:
        source_dir: Source directory path
        cmake_presets_file: Path to the CMakePresets.json file

    Returns:
        A new MacroResolver instance
    """
    if cmake_presets_file:
        return MacroResolver("", cmake_presets_file)
    elif source_dir:
        # Create a fake CMakePresets.json path to set source_dir correctly
        return MacroResolver(os.path.join(source_dir, "CMakePresets.json"))
    else:
        return MacroResolver()


def resolve_macros_in_preset(
    preset: dict[str, Any],
    preset_type: str,
    source_dir: str = "",
    cmake_presets_file: str = "",
    relative_paths: bool = False,
    file_paths: dict[str, str] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Convenience function to resolve macros in a preset.

    Args:
        preset: Preset dictionary
        preset_type: Type of preset
        source_dir: Source directory path
        cmake_presets_file: Path to the CMakePresets.json file
        relative_paths: If True, paths are made relative to source directory
        file_paths: Dictionary mapping preset names to file paths
        env: Additional environment variables

    Returns:
        A new preset with all macros resolved
    """
    if cmake_presets_file:
        resolver = MacroResolver("", cmake_presets_file)
    elif source_dir:
        resolver = MacroResolver(os.path.join(source_dir, "CMakePresets.json"))
    else:
        resolver = MacroResolver()

    return resolver.resolve_in_preset(preset, preset_type, relative_paths, env, file_paths)


def resolve_macros_in_string(value: str, context: dict[str, Any]) -> str:
    """
    Convenience function to resolve macros in a string.

    Args:
        value: String containing macros
        context: Context dictionary with macro values

    Returns:
        String with macros resolved
    """
    resolver = MacroResolver()
    return resolver.resolve_string(value, context)
