import copy
import os
import platform
import re
from typing import Any, cast

from . import logger as mainLogger

logger = mainLogger.getChild(__name__)


class MacroResolver:
    """Class for resolving macros in CMake preset values."""

    def __init__(self, source_dir: str = ""):
        """
        Initialize the macro resolver.

        Args:
            source_dir: Path to the source directory
        """
        self.source_dir = source_dir or os.getcwd()

    def resolve_in_preset(
        self,
        preset: dict[str, Any],
        preset_type: str,
        file_paths: dict[str, str] | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Resolve all macros in a preset.

        Args:
            preset: The preset dictionary
            preset_type: Type of preset (configure, build, test, etc.)
            file_paths: Dictionary mapping preset names to file paths
            extra_env: Optional environment variables to use for resolution

        Returns:
            A new preset with all macros resolved
        """
        # Deep copy the preset to avoid modifying the original
        resolved_preset = copy.deepcopy(preset)

        # Build context for macro resolution
        context = self._build_context(preset, preset_type, file_paths, extra_env)

        # Recursively resolve macros in all values
        self._resolve_recursive(resolved_preset, context)

        return resolved_preset

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
        """
        Resolve macros in a string based on the provided context.

        Args:
            value: String potentially containing macros
            context: Dictionary with macro values

        Returns:
            String with resolved macros
        """
        result = value

        # Process standard macros like ${sourceDir}
        for match in re.finditer(r"\${([^}]+)}", value):
            macro_name = match.group(1)
            if macro_name in context:
                result = result.replace(f"${{{macro_name}}}", str(context[macro_name]))

        # Process environment variables like $env{PATH}
        for match in re.finditer(r"\$env{([^}]+)}", value):
            env_name = match.group(1)
            if "env" in context and env_name in context["env"]:
                result = result.replace(f"$env{{{env_name}}}", context["env"].get(env_name, ""))
            else:
                result = result.replace(f"$env{{{env_name}}}", "")

        # Process parent environment variables like $penv{PATH}
        for match in re.finditer(r"\$penv{([^}]+)}", value):
            env_name = match.group(1)
            if "penv" in context and env_name in context["penv"]:
                result = result.replace(f"$penv{{{env_name}}}", context["penv"].get(env_name, ""))
            else:
                result = result.replace(f"$penv{{{env_name}}}", "")

        # We identify but don't actually resolve vendor macros
        vendor_macros = re.findall(r"\$vendor{([^}]+)}", value)
        if vendor_macros:
            logger.warning(f"String contains vendor macros which cannot be resolved: {vendor_macros}")

        return result


def create_resolver(source_dir: str = "") -> MacroResolver:
    """
    Create a new MacroResolver instance.

    Args:
        source_dir: Source directory path

    Returns:
        A new MacroResolver instance
    """
    return MacroResolver(source_dir)


def resolve_macros_in_preset(
    preset: dict[str, Any],
    preset_type: str,
    source_dir: str = "",
    file_paths: dict[str, str] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Convenience function to resolve macros in a preset.

    Args:
        preset: Preset dictionary
        preset_type: Type of preset
        source_dir: Source directory path
        file_paths: Dictionary mapping preset names to file paths
        env: Additional environment variables

    Returns:
        A new preset with all macros resolved
    """
    resolver = create_resolver(source_dir)
    return resolver.resolve_in_preset(preset, preset_type, file_paths, env)


def resolve_macros_in_string(value: str, context: dict[str, Any]) -> str:
    """
    Convenience function to resolve macros in a string.

    Args:
        value: String containing macros
        context: Context dictionary with macro values

    Returns:
        String with macros resolved
    """
    resolver = create_resolver()
    return resolver.resolve_string(value, context)
