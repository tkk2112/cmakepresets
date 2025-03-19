[//]: # (x-release-please-start-version)
# CMakePresets 0.3.1
[//]: # (x-release-please-end)


A Python library and CLI tool for working with CMakePresets.json configuration files in CMake projects.

## About

CMakePresets is a utility that helps you inspect and work with CMake preset configurations. It provides both a Python API for programmatic access and a command-line interface for interactive use.

## Features

- Parse and analyze CMakePresets.json files
- List all available presets of different types (configure, build, test, package, workflow)
- Show detailed information about specific presets
- Find related presets (e.g., build presets that use a specific configure preset)
- Display inheritance relationships between presets
- Output in different formats (rich tables, plain text, JSON)

## Installation

```bash
pip install cmakepresets
```

## Python API

```python
from cmakepresets import CMakePresets

# Load presets from a file or directory
presets = CMakePresets("path/to/CMakePresets.json")
# or
presets = CMakePresets("path/to/project/directory")

# Access preset data
configure_presets = presets.configure_presets
build_presets = presets.build_presets

# Get preset by name
preset = presets.get_preset_by_name("configure", "my-preset")

# Get preset tree showing hierarchical relationships
preset_tree = presets.get_preset_tree()

# Get flattened preset with all inherited properties resolved
flattened = presets.flatten_preset("configure", "my-preset")
```


## CLI Usage

### List all presets

```bash
cmakepresets --file CMakePresets.json list
cmakepresets --directory /path/to/project list
```

### List specific types of presets

```bash
cmakepresets --file CMakePresets.json list --type configure
```

### Show details of a specific preset

```bash
cmakepresets --file CMakePresets.json show my-preset
cmakepresets --file CMakePresets.json show my-preset --type configure
```

### Show in JSON format

```bash
cmakepresets --file CMakePresets.json show my-preset --json
```

### Find related presets

```bash
cmakepresets --file CMakePresets.json related my-configure-preset
cmakepresets --file CMakePresets.json related my-configure-preset --type build
```

### Script-friendly output

```bash
cmakepresets --file CMakePresets.json related my-configure-preset --plain
```
