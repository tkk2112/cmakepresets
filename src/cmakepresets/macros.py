import copy
import os
import platform
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from . import logger as mainLogger
from .paths import CMakeRoot

logger = mainLogger.getChild(__name__)


class MacroResolver:
    """Class for resolving macros in CMake preset values."""

    def __init__(self, root: CMakeRoot = None):
        """
        Initialize the macro resolver.

        Args:
            root: CMakeRoot instance containing source directory and presets file paths
        """
        if root is None:
            root = CMakeRoot(Path.cwd())
        self.source_dir = root.source_dir
        self.presets_file_path = root.presets_file

    def resolve_in_preset(
        self,
        preset: dict[str, Any],
        extra_env: dict[str, str] | None = None,
        file_paths: Mapping[str, str | Path] | None = None,
    ) -> dict[str, Any]:
        """
        Resolve all macros in a preset.

        Args:
            preset: The preset dictionary
            extra_env: Optional environment variables to use for resolution
            file_paths: Dictionary mapping preset names to file paths

        Returns:
            A new preset with all macros resolved
        """
        # Deep copy the preset to avoid modifying the original
        resolved_preset = copy.deepcopy(preset)

        # Build initial context for macro resolution
        context = self._build_context(preset, file_paths, extra_env)

        # Process cache variables first to allow for overrides
        context = self._process_cache_variables(resolved_preset, context)

        # Process the rest of the preset with the updated context
        self._process_remaining_values(resolved_preset, context)

        return resolved_preset

    def _process_cache_variables(self, preset: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Resolve cacheVariables and update context."""
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
                updated_context["sourceDir"] = Path(source_dir_override)
                # Update related paths
                updated_context["sourceParentDir"] = Path(source_dir_override).parent
                updated_context["sourceDirName"] = Path(source_dir_override).name

        return updated_context

    def _process_remaining_values(self, preset: dict[str, Any], context: dict[str, Any]) -> None:
        """Resolve remaining preset values."""
        for key, value in list(preset.items()):
            if key != "cacheVariables":  # Skip cache variables as they were already resolved
                preset[key] = self._resolve_recursive(value, context)

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
        file_paths: Mapping[str, str | Path] | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Build context information for macro resolution."""

        context = self._create_basic_context(preset)

        # Add generator information if available
        if "generator" in preset:
            context["generator"] = preset["generator"]

        # Add file directory information if available
        preset_name = preset.get("name", "")
        if file_paths and preset_name and preset_name in file_paths:
            filepath = file_paths[preset_name]
            if filepath:
                context["fileDir"] = Path(filepath).parent
        elif self.presets_file_path:
            context["fileDir"] = self.presets_file_path

        # Add environment information
        env_context = self._get_environment_context(preset, extra_env)
        context.update(env_context)

        return context

    def _create_basic_context(self, preset: dict[str, Any]) -> dict[str, Any]:
        """Create basic context with standard macros."""
        source_dir = self.source_dir
        source_parent_dir = self.source_dir.parent

        return {
            "sourceDir": source_dir,
            "sourceParentDir": source_parent_dir,
            "sourceDirName": self.source_dir.name,
            "presetName": preset.get("name", ""),
            "hostSystemName": platform.system(),
            "dollar": "$",
            "pathListSep": ":" if platform.system() != "Windows" else ";",
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

    def _replace_macro(self, match: re.Match[str], context: dict[str, Any]) -> str:
        macro_name: str = match.group(1)
        context_value = context.get(macro_name, match.group(0))
        # Convert Path objects to strings for substitution
        if isinstance(context_value, Path):
            return str(context_value)
        return str(context_value)

    def _replace_env(self, match: re.Match[str], context: dict[str, Any]) -> str:
        env_name: str = match.group(1)
        env_dict = context.get("env", {})
        if env_name in env_dict:
            return str(env_dict[env_name])
        else:
            return match.group(0)  # Return the original macro if not found

    def _replace_penv(self, match: re.Match[str], context: dict[str, Any]) -> str:
        env_name: str = match.group(1)
        penv_dict = context.get("penv", {})
        if env_name in penv_dict:
            return str(penv_dict[env_name])
        else:
            return match.group(0)  # Return the original macro if not found

    def _normalize_path(self, path_str: str) -> str:
        """Normalize a path string if it contains relative path segments."""
        if "/" in path_str and "../" in path_str and not path_str.startswith("$"):
            try:
                return str(Path(path_str).resolve())
            except (ValueError, OSError):
                pass
        return path_str

    def resolve_string(self, value: str, context: dict[str, Any], depth: int = 0) -> str:
        """Resolve all macros in a string."""
        # Prevent infinite recursion
        if depth > 10:
            logger.warning(f"Maximum macro resolution depth reached for: {value}")
            return value

        # Replace macro references
        result = re.sub(r"\${([^}]+)}", lambda m: self._replace_macro(m, context), value)

        # Replace environment variable references
        result = re.sub(r"\$env{([^}]+)}", lambda m: self._replace_env(m, context), result)
        result = re.sub(r"\$penv{([^}]+)}", lambda m: self._replace_penv(m, context), result)

        # Normalize paths
        result = self._normalize_path(result)

        # Remove "./" prefix from paths
        if result.startswith("./") and not result.startswith("$"):
            result = result[2:]

        # Check for vendor macros
        if re.search(r"\$vendor{([^}]+)}", result):
            vendor_macros = re.findall(r"\$vendor{([^}]+)}", result)
            logger.warning(f"String contains vendor macros which cannot be resolved: {vendor_macros}")

        # If there are still macros to resolve, call recursively
        if re.search(r"\${|\$env{|\$penv{", result):
            return self.resolve_string(result, context, depth + 1)

        return result


def create_resolver(path_input: str | Path = "") -> MacroResolver:
    """
    Create a new MacroResolver instance.

    Args:
        path_input: If the given path ends with '.json' it is treated as a file; otherwise as a directory.

    Returns:
        A new MacroResolver instance.
    """
    return MacroResolver(CMakeRoot(path_input) if path_input else None)


def resolve_macros_in_preset(
    preset: dict[str, Any],
    path_input: str | Path | CMakeRoot,
    file_paths: Mapping[str, str | Path] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Convenience function to resolve macros in a preset.

    Args:
        preset: Preset dictionary
        path_input: Path to source directory, CMakePresets.json file, or a CMakeRoot instance
        file_paths: Dictionary mapping preset names to file paths
        env: Additional environment variables

    Returns:
        A new preset with all macros resolved
    """
    if not isinstance(path_input, CMakeRoot):
        root = CMakeRoot(path_input)
    else:
        root = path_input

    return MacroResolver(root).resolve_in_preset(preset, env, file_paths)


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
