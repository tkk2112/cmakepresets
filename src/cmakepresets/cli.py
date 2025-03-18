import argparse
import json
import sys
from typing import Any, Final

from rich.table import Table
from rich.tree import Tree

from . import console, log
from . import logger as mainLogger
from .presets import CMakePresets

logger: Final = mainLogger.getChild(__name__)

# Base preset type names without "Presets" suffix for CLI
CLI_PRESET_TYPES: Final = ["configure", "build", "test", "package", "workflow"]


def create_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(description="CMake Presets utility for working with CMakePresets.json files")

    # Source group (file or directory)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--file", "-f", help="Path to CMakePresets.json file")
    source_group.add_argument("--directory", "-d", help="Directory containing CMakePresets.json")

    # Verbosity
    parser.add_argument("--verbose", "-v", action="count", default=0, help="Increase verbosity (can be used multiple times)")

    # Subcommands for different operations
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # List command
    list_parser = subparsers.add_parser("list", help="List all presets with optional filtering")
    list_parser.add_argument(
        "--type",
        "-t",
        choices=["configure", "build", "test", "package", "workflow"],
        default="all",
        help="Type of presets to list (default: all)",
    )
    list_parser.add_argument("--show-hidden", action="store_true", help="Show hidden presets")
    list_parser.add_argument("--flat", action="store_true", help="Show flat list without relationships")

    # Show command
    show_parser = subparsers.add_parser("show", help="Show details of a specific preset")
    show_parser.add_argument("preset_name", help="Name of the preset to display")
    show_parser.add_argument("--type", "-t", choices=CLI_PRESET_TYPES, help="Type of preset (optional if name is unique)")
    show_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    show_parser.add_argument("--flatten", action="store_true", help="Show flattened preset with all inherited values resolved")

    # Related command
    related_parser = subparsers.add_parser("related", help="Show presets related to a specific configure preset")
    related_parser.add_argument("configure_preset", help="Name of the configure preset")
    related_parser.add_argument("--type", "-t", choices=["build", "test", "package"], default="all", help="Type of related presets to show (default: all)")
    related_parser.add_argument("--show-hidden", action="store_true", help="Show hidden presets")
    related_parser.add_argument("--plain", "-p", action="store_true", help="Output in a simple format suitable for parsing in scripts")

    return parser


def get_presets_by_type(presets: CMakePresets, preset_type: str) -> list[dict[str, Any]]:
    """Get presets of a specific type."""
    if preset_type == "configure":
        return presets.configure_presets
    elif preset_type == "build":
        return presets.build_presets
    elif preset_type == "test":
        return presets.test_presets
    elif preset_type == "package":
        return presets.package_presets
    elif preset_type == "workflow":
        return presets.workflow_presets
    return []


def handle_list_command(presets: CMakePresets, args: argparse.Namespace) -> int:
    """Handle the 'list' command."""
    if args.flat or args.type != "all":
        return _display_flat_preset_list(presets, args)
    else:
        return _display_tabular_preset_list(presets, args)


def _display_flat_preset_list(presets: CMakePresets, args: argparse.Namespace) -> int:
    """Display a flat list of presets."""
    preset_types = [args.type] if args.type != "all" else CLI_PRESET_TYPES

    console.print("[bold]CMake Presets:[/bold]")
    found_presets = False

    for preset_type in preset_types:
        preset_list = get_presets_by_type(presets, preset_type)

        if not preset_list:
            continue

        # Filter presets
        filtered_presets = _filter_presets(preset_list, args.show_hidden)

        if filtered_presets:
            found_presets = True
            console.print(f"\n[bold]{preset_type.capitalize()} Presets:[/bold]")
            for preset in filtered_presets:
                _print_preset_item(preset)

    if not found_presets:
        console.print("[yellow]No presets found matching your criteria[/yellow]")

    return 0


def _filter_presets(preset_list: list[dict[str, Any]], show_hidden: bool) -> list[dict[str, Any]]:
    """Filter presets based on visibility."""
    filtered = []
    for preset in preset_list:
        # Skip hidden presets if not requested
        if not show_hidden and preset.get("hidden", False):
            continue
        filtered.append(preset)
    return filtered


def _print_preset_item(preset: dict[str, Any]) -> None:
    """Print a single preset item in the flat list."""
    name = preset.get("name", "Unnamed")
    description = preset.get("description", "")

    # Mark default and hidden presets
    markers = []
    if preset.get("default", False):
        markers.append("[green]DEFAULT[/green]")

    marker_str = f" {' '.join(markers)}" if markers else ""

    # Style hidden presets differently rather than adding a marker
    name_style = "dim" if preset.get("hidden", False) else ""
    name_display = f"[{name_style}]{name}[/{name_style}]" if name_style else name

    console.print(f"  • [bold cyan]{name_display}[/bold cyan]{marker_str}")

    if description:
        console.print(f"    {description}")


def _display_tabular_preset_list(presets: CMakePresets, args: argparse.Namespace) -> int:
    """Display presets in a tabular view."""
    preset_tree = presets.get_preset_tree()

    if not preset_tree:
        console.print("[yellow]No presets found[/yellow]")
        return 0

    # Create a table with headers for each preset type
    table = _create_presets_table()

    # Sort presets by name for consistent display
    sorted_names = sorted(preset_tree.keys())

    # Track if we've added at least one row
    rows_added = False

    for name in sorted_names:
        data = preset_tree[name]
        config_preset = data["preset"]

        # Skip hidden presets if not requested
        if not args.show_hidden and config_preset.get("hidden", False):
            continue

        # Add a separator before each group (except the first)
        if rows_added:
            _add_separator_row(table)
        else:
            rows_added = True

        _add_preset_group_to_table(table, name, config_preset, data["dependents"])

    console.print(table)
    return 0


def _create_presets_table() -> Table:
    """Create the table for displaying presets."""
    table = Table(title="CMake Presets")
    table.add_column("Configure", style="cyan", justify="left")
    table.add_column("Build", style="blue", justify="left")
    table.add_column("Test", style="green", justify="left")
    return table


def _add_separator_row(table: Table) -> None:
    """Add a separator row to the table."""
    separator = "─" * 40
    table.add_row(f"[dim]{separator}[/dim]", f"[dim]{separator}[/dim]", f"[dim]{separator}[/dim]")


def _add_preset_group_to_table(table: Table, name: str, config_preset: dict[str, Any], dependents: dict[str, list[dict[str, Any]]]) -> None:
    """Add a preset group (configure preset and its dependents) to the table."""
    build_presets = dependents.get("buildPresets", [])
    test_presets = dependents.get("testPresets", [])

    # Format configure preset name with build/test counts
    config_display = _format_configure_preset_display(name, config_preset, build_presets, test_presets)

    # Format build preset names
    build_display = _format_dependent_presets_display(build_presets)

    # Format test preset names
    test_display = _format_dependent_presets_display(test_presets)

    # Add row to table
    table.add_row(config_display, build_display, test_display)


def _format_configure_preset_display(
    name: str,
    config_preset: dict[str, Any],
    build_presets: list[dict[str, Any]],
    test_presets: list[dict[str, Any]],
) -> str:
    """Format the display string for a configure preset."""
    # Style hidden presets differently rather than adding a marker
    config_style = "dim" if config_preset.get("hidden", False) else ""
    config_display = f"[{config_style}]{name}[/{config_style}]" if config_style else name

    # Add count info
    build_count = len(build_presets)
    test_count = len(test_presets)
    if build_count > 1 or test_count > 1:
        counts = []
        if build_count > 1:
            counts.append(f"{build_count} builds")
        if test_count > 1:
            counts.append(f"{test_count} tests")
        count_info = ", ".join(counts)
        config_display += f" [dim]({count_info})[/dim]"

    # Add default marker if applicable
    if config_preset.get("default", False):
        config_display += " [green][D][/green]"

    return config_display


def _format_dependent_presets_display(presets: list[dict[str, Any]]) -> str:
    """Format the display string for dependent presets (build or test)."""
    if not presets:
        return ""

    names = []
    for preset in presets:
        name = preset.get("name", "")
        if name:
            # Style hidden presets differently
            style = "dim" if preset.get("hidden", False) else ""
            formatted = f"[{style}]{name}[/{style}]" if style else name

            # Only add default marker
            if preset.get("default", False):
                formatted += " [green][D][/green]"

            names.append(formatted)
    return "\n".join(names)


def handle_show_command(presets: CMakePresets, args: argparse.Namespace) -> int:
    """Handle the 'show' command."""
    preset_name = args.preset_name

    # Find the preset
    found_preset, found_type = _find_preset(presets, preset_name, args.type)

    if not found_preset or found_type is None:
        console.print(f"[bold red]Error:[/bold red] Preset '{preset_name}' not found")
        return 1

    # If flatten option is specified, get the flattened preset
    if args.flatten:
        found_preset = presets.flatten_preset(found_type, preset_name)

    # Output as JSON if requested
    if args.json:
        console.print(json.dumps(found_preset, indent=2))
        return 0

    console.print(f"[bold]Preset: [bold cyan]{preset_name}[/bold cyan] ({found_type})[/bold]\n")

    # Display property sources and inheritance info
    property_sources: dict[str, str] = {}
    if not args.flatten:
        _show_inheritance_info(presets, found_preset, found_type, preset_name, property_sources)

    # Display the preset details
    _show_preset_details(presets, found_preset, found_type, preset_name, property_sources, args.flatten)

    return 0


def _find_preset(presets: CMakePresets, preset_name: str, preset_type: str | None) -> tuple[dict[str, Any] | None, str | None]:
    """Find a preset by name and type."""
    found_preset = None
    found_type: str | None = None

    # Fix for --type parameter
    if preset_type:
        # If type is specified, look only in that preset type
        found_preset = presets.get_preset_by_name(preset_type, preset_name)
        found_type = preset_type
    else:
        # If type is not specified, look in all preset types
        for pt in CLI_PRESET_TYPES:
            preset = presets.get_preset_by_name(pt, preset_name)
            if preset:
                found_preset = preset
                found_type = pt
                break

    return found_preset, found_type


def _show_inheritance_info(presets: CMakePresets, found_preset: dict[str, Any], found_type: str, preset_name: str, property_sources: dict[str, str]) -> None:
    """Show inheritance information for a preset."""
    inheritance_chain = []
    if "inherits" in found_preset:
        # Get the inheritance information
        inheritance_chain = presets.get_preset_inheritance_chain(found_type, preset_name)
        direct_inherits = found_preset.get("inherits", [])
        if isinstance(direct_inherits, str):
            direct_inherits = [direct_inherits]

        # Display inheritance as a tree using Rich's Tree class
        console.print("[bold]Inheritance tree:[/bold]")

        # Create a root tree with the current preset
        tree = Tree(f"[bold cyan]{preset_name}[/bold cyan]", guide_style="dim")

        # Build the inheritance tree for each direct parent
        for parent_name in direct_inherits:
            _build_inheritance_tree(presets, found_type, parent_name, tree)

        # Print the tree
        console.print(tree)
        console.print("")

        # Get the full inheritance chain and build a map of property sources
        full_chain = inheritance_chain.copy()
        full_chain.append(found_preset)

        # Map properties in the inheritance chain (from earliest parent to latest)
        for preset in full_chain:
            preset_name = preset.get("name", "Unnamed")
            # Use a more thorough mapping that catches all properties
            _map_all_properties(preset, preset_name, property_sources)


def _build_inheritance_tree(presets: CMakePresets, preset_type: str, preset_name: str, parent_tree: Tree) -> None:
    """
    Recursively build the inheritance tree visualization for a preset.

    Args:
        presets: CMakePresets instance
        preset_type: Type of preset
        preset_name: Name of preset to add to tree
        parent_tree: Parent tree node to attach to
    """
    # Create a branch for this preset
    branch = parent_tree.add(f"[cyan]{preset_name}[/cyan]")

    # Get the preset and check for further inheritance
    preset = presets.get_preset_by_name(preset_type, preset_name)
    if not preset or "inherits" not in preset:
        return

    # Handle both string and array inheritance
    inherits = preset["inherits"]
    if isinstance(inherits, str):
        inherits = [inherits]

    # Recursively build tree for each parent preset
    for parent in inherits:
        _build_inheritance_tree(presets, preset_type, parent, branch)


def _show_preset_details(
    presets: CMakePresets,
    found_preset: dict[str, Any],
    found_type: str,
    preset_name: str,
    property_sources: dict[str, str],
    is_flattened: bool,
) -> None:
    """Show detailed information about a preset."""
    table = Table(show_header=False, padding=(0, 1), box=None)
    table.add_column("Property", style="bold")
    table.add_column("Value")
    table.add_column("Source", style="dim")

    # Add all preset properties to the table, including inherited properties
    if not is_flattened:
        # Get flattened preset to show all properties, but keep track of sources
        flattened = presets.flatten_preset(found_type, preset_name)
        _add_properties_to_table(table, flattened, property_sources)
    else:
        _add_properties_to_table(table, found_preset, property_sources)

    console.print(table)


def _map_all_properties(preset: dict[str, Any], preset_name: str, property_sources: dict[str, str], prefix: str = "") -> None:
    """
    Map all properties and their sources, ensuring all nested fields are captured.
    """
    for key, value in preset.items():
        if key == "name":
            continue

        property_path = f"{prefix}{key}" if prefix else key

        # Only update if not already tracked (earlier sources take precedence)
        if property_path not in property_sources:
            property_sources[property_path] = preset_name

        # Handle based on value type
        if isinstance(value, dict):
            _map_dict_properties(value, preset_name, property_sources, property_path)
        elif isinstance(value, list):
            _map_list_properties(value, preset_name, property_sources, property_path)


def _map_dict_properties(value: dict[str, Any], preset_name: str, property_sources: dict[str, str], property_path: str) -> None:
    """Map properties in a dictionary."""
    for nested_key, nested_value in value.items():
        nested_path = f"{property_path}.{nested_key}"
        if nested_path not in property_sources:
            property_sources[nested_path] = preset_name

        if isinstance(nested_value, dict):
            _map_all_properties({nested_key: nested_value}, preset_name, property_sources, f"{property_path}.")


def _map_list_properties(value: list[Any], preset_name: str, property_sources: dict[str, str], property_path: str) -> None:
    """Map properties in a list."""
    for i, item in enumerate(value):
        if isinstance(item, dict):
            item_path = f"{property_path}[{i}]"
            for item_key, item_value in item.items():
                item_key_path = f"{item_path}.{item_key}"
                if item_key_path not in property_sources:
                    property_sources[item_key_path] = preset_name

                if isinstance(item_value, dict):
                    _map_all_properties({item_key: item_value}, preset_name, property_sources, f"{item_path}.")


def _add_properties_to_table(table: Table, preset: dict[str, Any], property_sources: dict[str, str], prefix: str = "", indent_level: int = 0) -> None:
    """
    Add properties to the display table, with sources if available.
    """
    indent = "  " * indent_level
    current_preset_name = preset.get("name", "")

    for key, value in preset.items():
        if key == "name":
            continue

        # Skip 'hidden' property unless it's from the current preset
        if key == "hidden" and property_sources.get(key) != current_preset_name:
            continue

        property_path = f"{prefix}{key}" if prefix else key
        source = _get_property_source(property_sources, property_path, preset)

        # Handle different value types
        if isinstance(value, bool):
            _add_bool_property(table, key, value, source, indent)
        elif isinstance(value, dict):
            _add_dict_property(table, key, value, property_sources, property_path, source, indent, indent_level)
        elif isinstance(value, list):
            _add_list_property(table, key, value, property_sources, property_path, source, indent, indent_level)
        else:
            _add_simple_property(table, key, value, source, indent)


def _get_property_source(property_sources: dict[str, str], property_path: str, preset: dict[str, Any]) -> str:
    """Get the source of a property."""
    source = property_sources.get(property_path, "")
    if source and source == preset.get("name", ""):
        source = ""  # Don't show source if it's from the current preset
    return source


def _add_bool_property(table: Table, key: str, value: bool, source: str, indent: str) -> None:
    """Add a boolean property to the table."""
    value_str = f"{indent}[green]True[/green]" if value else f"{indent}[red]False[/red]"
    table.add_row(f"{indent}{key}", value_str, source)


def _add_dict_property(
    table: Table,
    key: str,
    value: dict[str, Any],
    property_sources: dict[str, str],
    property_path: str,
    source: str,
    indent: str,
    indent_level: int,
) -> None:
    """Add a dictionary property to the table."""
    table.add_row(f"{indent}{key}", f"{indent}{{", source)
    _add_properties_to_table(table, value, property_sources, f"{property_path}.", indent_level + 1)
    table.add_row("", f"{indent}}}", "")


def _add_list_property(
    table: Table,
    key: str,
    value: list[Any],
    property_sources: dict[str, str],
    property_path: str,
    source: str,
    indent: str,
    indent_level: int,
) -> None:
    """Add a list property to the table."""
    if not value:
        table.add_row(f"{indent}{key}", f"{indent}[]", source)
    elif all(not isinstance(item, (dict, list)) for item in value):
        # Simple list with primitive values
        value_str = json.dumps(value, indent=2)
        table.add_row(f"{indent}{key}", f"{indent}{value_str}", source)
    else:
        # Complex list with objects
        _add_complex_list_property(table, key, value, property_sources, property_path, source, indent, indent_level)


def _add_complex_list_property(
    table: Table,
    key: str,
    value: list[Any],
    property_sources: dict[str, str],
    property_path: str,
    source: str,
    indent: str,
    indent_level: int,
) -> None:
    """Add a complex list property (containing dicts) to the table."""
    table.add_row(f"{indent}{key}", f"{indent}[", source)
    for i, item in enumerate(value):
        if isinstance(item, dict):
            table.add_row("", f"{indent}  {{", "")
            _add_properties_to_table(table, item, property_sources, f"{property_path}[{i}].", indent_level + 2)
            table.add_row("", f"{indent}  }},", "")
        else:
            table.add_row("", f"{indent}  {json.dumps(item)},", "")
    table.add_row("", f"{indent}]", "")


def _add_simple_property(table: Table, key: str, value: Any, source: str, indent: str) -> None:
    """Add a simple property to the table."""
    value_str = f"{indent}{value}"
    table.add_row(f"{indent}{key}", value_str, source)


# Helper functions for the "related" command
def _get_configure_preset(presets: CMakePresets, preset_name: str, show_error: bool = True) -> dict[str, Any] | None:
    """Get a configure preset.

    Returns:
        Configure preset or None if not found
    """
    # Find the configure preset
    configure_preset = presets.get_preset_by_name("configure", preset_name)
    if not configure_preset and show_error:
        console.print(f"[bold red]Error:[/bold red] Configure preset '{preset_name}' not found")
    return configure_preset


def _filter_presets_by_visibility(presets_list: list[dict[str, Any]], show_hidden: bool) -> list[dict[str, Any]]:
    """Filter presets based on visibility settings."""
    if not show_hidden:
        return [p for p in presets_list if not p.get("hidden", False)]

    # Style hidden presets with dim formatting when they are shown
    result = []
    for p in presets_list:
        # Create a copy to avoid modifying the original
        preset = p.copy()
        if preset.get("hidden", False):
            # Style hidden preset names with dim formatting
            original_name = preset.get("name", "Unnamed")
            preset["name"] = f"[dim]{original_name}[/dim]"
        result.append(preset)
    return result


def _print_rich_related_output(
    configure_preset_name: str,
    related_presets: dict[str, list[dict[str, Any]]],
    preset_types: list[str],
    show_hidden: bool,
) -> bool:
    """Print rich formatted output for related presets. Returns True if any presets were found."""
    console.print(f"Presets related to configurePreset: [bold green]{configure_preset_name}[/bold green]")

    found_any = False
    for preset_type in preset_types:
        presets_list = related_presets.get(preset_type, [])

        # Filter based on visibility
        filtered_presets = _filter_presets_by_visibility(presets_list, show_hidden)

        if filtered_presets:
            found_any = True
            preset_names = [p.get("name", "Unnamed") for p in filtered_presets]
            plural = "s" if len(preset_names) > 1 else ""
            console.print(f"{preset_type}Preset{plural}: [green]{', '.join(preset_names)}[/green]")
        else:
            # Only show empty types if explicitly requested
            console.print(f"{preset_type}Preset: [dim]none[/dim]")

    return found_any


def _get_available_preset_types(related_presets: dict[str, list[dict[str, Any]]], show_hidden: bool) -> list[str]:
    """Get a list of available preset types that have at least one preset."""
    available_types = []

    for preset_type in ["build", "test", "package"]:
        presets_list = related_presets.get(preset_type, [])
        if not presets_list:
            continue

        # Filter based on visibility
        filtered_presets = [p for p in presets_list if show_hidden or not p.get("hidden", False)]
        if filtered_presets:
            available_types.append(preset_type)

    return available_types


def _get_preset_names_for_type(related_presets: dict[str, list[dict[str, Any]]], preset_type: str, show_hidden: bool) -> list[str]:
    """Get preset names for a specific preset type."""
    presets_list = related_presets.get(preset_type, [])

    # Filter based on visibility
    filtered_presets = [p for p in presets_list if show_hidden or not p.get("hidden", False)]

    # Extract names
    return [p.get("name", "Unnamed") for p in filtered_presets]


# Simplified handler functions
def _handle_related_plain_output(args: argparse.Namespace, related_presets: dict[str, list[dict[str, Any]]]) -> int:
    """Handle plain output mode for scripts."""
    if args.type == "all":
        # Get available types and print them
        available_types = _get_available_preset_types(related_presets, args.show_hidden)
        if available_types:
            print(" ".join(available_types))
            return 0
        return 1
    else:
        # Get preset names for the specific type
        preset_names = _get_preset_names_for_type(related_presets, args.type, args.show_hidden)
        if preset_names:
            print(" ".join(preset_names))
            return 0
        return 1


def handle_related_command(presets: CMakePresets, args: argparse.Namespace) -> int:
    """Handle the 'related' command to show presets related to a specific configure preset."""
    # Use the find_related_presets method to get related presets
    preset_type = None if args.type == "all" else args.type
    related_presets = presets.find_related_presets(args.configure_preset, preset_type)

    if related_presets is None:
        if not args.plain:
            console.print(f"[bold red]Error:[/bold red] Configure preset '{args.configure_preset}' not found")
        return 1

    # Handle plain output mode for scripts
    if args.plain:
        return _handle_related_plain_output(args, related_presets)

    # Get preset types to display based on filter
    preset_types_to_display = [preset_type] if preset_type in ["build", "test", "package"] else ["build", "test", "package"]

    # Print rich formatted output
    found_any = _print_rich_related_output(args.configure_preset, related_presets, preset_types_to_display, args.show_hidden)

    # Error if the user specified a type that doesn't exist for this preset
    if args.type != "all" and not found_any:
        console.print(f"[bold red]Error:[/bold red] No {args.type} presets found for '{args.configure_preset}'")
        return 1

    return 0


def main() -> int:
    """Main entry point for the CLI application."""
    parser = create_parser()
    args = parser.parse_args()

    # Set up logging based on verbosity
    if args.verbose >= 3:
        mainLogger.setLevel(log.DEBUG)
        logger.debug("Debug logging enabled")
    elif args.verbose == 2:
        mainLogger.setLevel(log.INFO)
        logger.debug("Info logging enabled")
    elif args.verbose == 1:
        mainLogger.setLevel(log.WARNING)
        logger.debug("Info logging enabled")
    else:
        mainLogger.setLevel(log.ERROR)

    # Log some basic information at debug level
    logger.debug(f"Arguments: {args}")
    logger.debug(f"Logger level: {logger.level}")
    logger.debug(f"Handlers: {logger.handlers}")

    # If no command is provided, show help
    if not hasattr(args, "command") or not args.command:
        parser.print_help()
        return 1

    try:
        # Create CMakePresets instance from file or directory
        path = args.file if args.file else args.directory
        logger.info(f"Loading presets from {path}")
        presets = CMakePresets(path)
        logger.debug(f"Loaded {len(presets.configure_presets)} configure presets")
        logger.debug(f"Loaded {len(presets.build_presets)} build presets")
        logger.debug(f"Loaded {len(presets.test_presets)} test presets")

        # Handle commands
        if args.command == "list":
            return handle_list_command(presets, args)
        elif args.command == "show":
            return handle_show_command(presets, args)
        elif args.command == "related":
            return handle_related_command(presets, args)
        else:
            console.print(f"[bold red]Unknown command:[/bold red] {args.command}")
            return 1

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if args.verbose:
            logger.exception("An error occurred")
        return 1


if __name__ == "__main__":
    sys.exit(main())
