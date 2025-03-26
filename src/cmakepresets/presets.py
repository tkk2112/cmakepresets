from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final, cast

from . import logger as mainLogger
from .constants import BUILD, CONFIGURE, PACKAGE, PRESET_MAP, TEST, WORKFLOW
from .macros import resolve_macros_in_preset
from .parser import Parser
from .paths import CMakeRoot

logger: Final = mainLogger.getChild(__name__)


class CMakePresets:
    """Class for working with CMake presets data."""

    def __init__(self, path_input: str | Path | CMakeRoot):
        """
        Initialize with path to CMakePresets.json or CMakeRoot instance.

        Args:
            path_input: Either a string/Path to a CMakePresets.json file/directory,
                       or a CMakeRoot instance containing source directory and presets file paths

        Raises:
            FileNotFoundError: If the specified file or directory doesn't exist
            FileReadError: If a file cannot be read
            FileParseError: If a file cannot be parsed as JSON
            VersionError: If the version is not supported (< 2)
        """
        # Convert path_input to CMakeRoot if it's not already
        if not isinstance(path_input, CMakeRoot):
            self.root = CMakeRoot(path_input)
        else:
            self.root = path_input

        logger.debug(f"Parsing file: {self.root.presets_file}")
        self.parser = Parser()
        self.parser.parse_file(str(self.root.presets_file))
        logger.debug(f"Successfully parsed {len(self.parser.loaded_files)} preset files")

        # Log number of presets found
        for preset_type, key in PRESET_MAP.items():
            count = sum(1 for _ in self._iter_presets_of_type(key))
            logger.debug(f"Found {count} {preset_type} presets")

    @property
    def configure_presets(self) -> list[dict[str, Any]]:
        """Get all configure presets across all loaded files."""
        return list(self._iter_presets_of_type(PRESET_MAP[CONFIGURE]))

    @property
    def build_presets(self) -> list[dict[str, Any]]:
        """Get all build presets across all loaded files."""
        return list(self._iter_presets_of_type(PRESET_MAP[BUILD]))

    @property
    def test_presets(self) -> list[dict[str, Any]]:
        """Get all test presets across all loaded files."""
        return list(self._iter_presets_of_type(PRESET_MAP[TEST]))

    @property
    def package_presets(self) -> list[dict[str, Any]]:
        """Get all package presets across all loaded files."""
        return list(self._iter_presets_of_type(PRESET_MAP[PACKAGE]))

    @property
    def workflow_presets(self) -> list[dict[str, Any]]:
        """Get all workflow presets across all loaded files."""
        return list(self._iter_presets_of_type(PRESET_MAP[WORKFLOW]))

    def _iter_presets_of_type(self, preset_type: str) -> Iterator[dict[str, Any]]:
        """
        Iterate through all presets of a specific type across all loaded files.

        Args:
            preset_type: Type of preset (configurePresets, buildPresets, etc.)

        Yields:
            Each preset of the specified type
        """
        for filepath, file_data in self.parser.loaded_files.items():
            if preset_type in file_data:
                yield from file_data[preset_type]

    def get_configure_presets(self) -> list[dict[str, Any]]:
        """Get all configure presets."""
        return self.configure_presets

    def get_build_presets(self) -> list[dict[str, Any]]:
        """Get all build presets."""
        return self.build_presets

    def get_test_presets(self) -> list[dict[str, Any]]:
        """Get all test presets."""
        return self.test_presets

    def get_package_presets(self) -> list[dict[str, Any]]:
        """Get all package presets."""
        return self.package_presets

    def get_workflow_presets(self) -> list[dict[str, Any]]:
        """Get all workflow presets."""
        return self.workflow_presets

    def get_preset_by_name(self, preset_type: str, name: str) -> dict[str, Any] | None:
        """
        Get a specific preset by type and name.

        Args:
            preset_type: Type of preset (configure, build, test, package, workflow)
            name: Name of the preset

        Returns:
            Preset dict if found, None otherwise
        """
        logger.debug(f"Looking for {preset_type} preset with name '{name}'")
        preset_key = PRESET_MAP[preset_type]

        for filepath, file_data in self.parser.loaded_files.items():
            if preset_key not in file_data:
                continue

            for preset in file_data[preset_key]:
                if preset.get("name") == name:
                    logger.debug(f"Found preset '{name}' in file {filepath}")
                    return cast(dict[str, Any], preset)

        logger.debug(f"Preset '{name}' not found")
        return None

    def find_preset(self, name: str) -> dict[str, Any] | None:
        """
        Find a preset by name across all preset types.

        Args:
            name: Name of the preset to find

        Returns:
            The preset dict if found, None otherwise
        """
        for preset_type in PRESET_MAP:
            for preset in self._iter_presets_of_type(PRESET_MAP[preset_type]):
                if preset.get("name") == name:
                    return preset

        return None

    def get_preset_inheritance_chain(self, preset_type: str, preset_name: str) -> list[dict[str, Any]]:
        """
        Get the inheritance chain for a preset.

        Args:
            preset_type: Type of preset (configure, build, test, package, workflow)
            preset_name: Name of the preset

        Returns:
            List of preset dicts in inheritance order (base first, immediate parent last)
        """
        chain: list[dict[str, Any]] = []
        current = self.get_preset_by_name(preset_type, preset_name)

        if not current or "inherits" not in current:
            return chain

        # Handle both string and array inheritance
        inherits_values = current["inherits"]
        if isinstance(inherits_values, str):
            # Single inheritance
            inherits_values = [inherits_values]
        elif not isinstance(inherits_values, list):
            logger.warning(f"Unexpected 'inherits' format in preset {preset_name}: {inherits_values}")
            return chain

        # Process each parent in the inheritance list
        for parent_name in inherits_values:
            parent = self.get_preset_by_name(preset_type, parent_name)
            if parent:
                # Get the parent's inheritance chain first (recursive)
                parent_chain = self.get_preset_inheritance_chain(preset_type, parent_name)

                # Add the parent's chain and the parent itself
                # Avoid duplicates in the chain
                for p in parent_chain:
                    if p not in chain:  # Note: This does simple dict comparison
                        chain.append(p)

                if parent not in chain:
                    chain.append(parent)
            else:
                logger.warning(f"Could not find parent preset '{parent_name}' referenced by '{preset_name}'")

        return chain

    def flatten_preset(self, preset_type: str, preset_name: str) -> dict[str, Any]:
        """
        Get a preset with all inherited values resolved.

        Args:
            preset_type: Type of preset (configure, build, test, package, workflow)
            preset_name: Name of the preset

        Returns:
            Dict with all inherited properties flattened
        """
        preset = self.get_preset_by_name(preset_type, preset_name)
        if not preset:
            logger.warning(f"Could not find preset '{preset_name}' of type '{preset_type}'")
            return {}

        # Start with the base preset
        chain = self.get_preset_inheritance_chain(preset_type, preset_name)
        chain.append(preset)  # Add the preset itself

        return self._merge_presets_chain(chain, non_inheritable_properties=["inherits", "hidden"])

    def _merge_presets_chain(self, chain: list[dict[str, Any]], non_inheritable_properties: list[str]) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for p in chain:
            temp = {}
            for key, value in p.items():
                if key in non_inheritable_properties and p != chain[-1]:
                    continue
                if key == "inherits":
                    continue
                if isinstance(value, dict):
                    if key in merged and isinstance(merged[key], dict):
                        temp[key] = {**merged[key], **value}
                    else:
                        temp[key] = value.copy()
                else:
                    temp[key] = value
            merged.update(temp)
        return merged

    def get_dependent_presets(self, preset_type: str, preset_name: str) -> dict[str, list[dict[str, Any]]]:
        """
        Get presets that depend on a specific preset.

        Args:
            preset_type: Type of preset (configure, build, test, package, workflow)
            preset_name: Name of the preset

        Returns:
            Dict mapping preset types to lists of dependent presets
        """
        dependent_presets: dict[str, list[dict[str, Any]]] = {pt: [] for pt in PRESET_MAP.values()}

        # Only configure presets can be referenced by other preset types
        if preset_type != CONFIGURE:
            return dependent_presets

        for dep_type in [BUILD, TEST, PACKAGE]:
            dep_type_key = PRESET_MAP[dep_type]
            for preset in getattr(self, f"{dep_type}_presets"):
                # Direct dependency through configurePreset field
                if preset.get("configurePreset") == preset_name:
                    dependent_presets[dep_type_key].append(preset)
                    continue

                # Check for indirect dependency through inheritance
                if "inherits" in preset and "configurePreset" not in preset:
                    # Get the resolved configurePreset by flattening
                    flattened = self.flatten_preset(dep_type, preset.get("name", ""))
                    if flattened.get("configurePreset") == preset_name:
                        dependent_presets[dep_type_key].append(preset)

        return dependent_presets

    def get_preset_tree(self) -> dict[str, Any]:
        """
        Get a tree structure of presets, where configure presets are the roots,
        and build/test/package presets that depend on them are children.

        Returns:
            Dict mapping configure preset names to their dependent presets
        """
        tree = {}

        # Start with all configure presets
        for configure_preset in self.configure_presets:
            name = configure_preset.get("name")
            if name:
                dependent_presets: dict[str, list[dict[str, Any]]] = self.get_dependent_presets(CONFIGURE, name)
                tree[name] = {"preset": configure_preset, "dependents": dependent_presets}

        return tree

    def find_related_presets(self, configure_preset_name: str, preset_type: str | None = None) -> dict[str, list[dict[str, Any]]] | None:
        """
        Find presets related to a specific configure preset.

        Args:
            configure_preset_name: Name of the configure preset to find related presets for
            preset_type: Optional type filter ('build', 'test', 'package')

        Returns:
            Dictionary of related presets by type or None if preset not found
        """
        # Get the preset tree (contains relationship data)
        preset_tree = self.get_preset_tree()

        # Check if the configure preset exists
        if configure_preset_name not in preset_tree:
            logger.warning(f"Configure preset '{configure_preset_name}' not found")
            return None

        # Get the related presets data
        related_data = preset_tree[configure_preset_name]

        # Get the dependent presets
        dependent_presets = related_data["dependents"]

        # Filter by type if specified
        if preset_type:
            preset_key = f"{preset_type}Presets"
            if preset_key in dependent_presets:
                return {preset_type: dependent_presets[preset_key]}
            return {preset_type: []}

        # Return all related presets (build, test, package)
        return {
            BUILD: dependent_presets.get(PRESET_MAP[BUILD], []),
            TEST: dependent_presets.get(PRESET_MAP[TEST], []),
            PACKAGE: dependent_presets.get(PRESET_MAP[PACKAGE], []),
        }

    def resolve_macro_values(self, preset_type: str, preset_name: str) -> dict[str, Any]:
        """
        Resolve macro values in a preset.

        Args:
            preset_type: Type of preset (configure, build, test, etc.)
            preset_name: Name of the preset to resolve

        Returns:
            A new preset with all macros resolved
        """
        flattened = self.flatten_preset(preset_type, preset_name)

        # Get file paths to provide context for macros
        preset_file_paths = self._get_preset_file_paths()

        # Use the updated API
        return resolve_macros_in_preset(
            flattened,
            self.root,
            file_paths=preset_file_paths,
        )

    def _get_preset_file_paths(self) -> dict[str, str]:
        """Get mapping of preset names to their containing file paths."""
        file_paths: dict[str, str] = {}
        for filepath, file_data in self.parser.loaded_files.items():
            for preset_key in PRESET_MAP.values():
                if preset_key not in file_data:
                    continue
                for preset in file_data[preset_key]:
                    name = preset.get("name")
                    if name:
                        file_paths[name] = filepath
        return file_paths
