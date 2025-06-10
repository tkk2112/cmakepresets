[//]: # (x-release-please-start-version)
# CMakePresets 0.4.1
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

## Python API

```python
>>> # Set up the test environment (only needed for doctest)
>>> import os
>>> import sys
>>> sys.path.insert(0, '.')
>>> # Create a proper test environment
>>> from tests.decorators import CMakePresets_json
>>>
>>> # Create test preset content
>>> preset_content = '''{
...   "version": 4,
...   "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
...   "configurePresets": [
...     {
...       "name": "base",
...       "generator": "Ninja",
...       "binaryDir": "${sourceDir}/build/${presetName}",
...       "hidden": true
...     },
...     {
...       "name": "my-config",
...       "inherits": "base",
...       "cacheVariables": {
...         "CMAKE_BUILD_TYPE": "Debug"
...       }
...     }
...   ],
...   "buildPresets": [
...     {
...       "name": "my-build",
...       "configurePreset": "my-config"
...     }
...   ]
... }'''
>>>
>>> # Set up the test environment
>>> patcher = CMakePresets_json(preset_content)
>>> test_env = patcher.__enter__()  # This creates a fake filesystem with CMakePresets.json

>>> ###################################################################
>>> # Now we can import and use CMakePresets normally as in real code #
>>> ###################################################################
>>> # Python API Examples
>>> ####
>>> from cmakepresets import CMakePresets
>>> from cmakepresets.constants import CONFIGURE, PACKAGE

>>> # Load presets from a file (uses the fake filesystem)
>>> presets = CMakePresets("CMakePresets.json")
>>> print(len(presets.configure_presets))
2


>>> # Or load from a project directory
>>> presets = CMakePresets(".")
>>> print(len(presets.build_presets))
1


>>> # Access preset collections
>>> configure_presets = presets.configure_presets
>>> # List names of all configure presets
>>> [preset["name"] for preset in configure_presets]
['base', 'my-config']


>>> # Get related prests to the configurePreset 'my-config'
>>> related = presets.find_related_presets("my-config")
>>> print(related)
{'build': [{'name': 'my-build', 'configurePreset': 'my-config'}], 'test': [], 'package': []}

>>> # Get related packagePrests to 'my-config'
>>> related = presets.find_related_presets("my-config", PACKAGE)
>>> print(len(related[PACKAGE]))
0


>>> # Get a specific preset by name
>>> my_config = presets.get_preset_by_name(CONFIGURE, "my-config")
>>> my_config["name"]
'my-config'

>>> # Get flattened preset with all inherited properties resolved
>>> flattened = presets.flatten_preset(CONFIGURE, "my-config")

>>> # Print the original preset
>>> print(my_config)
{'name': 'my-config', 'inherits': 'base', 'cacheVariables': {'CMAKE_BUILD_TYPE': 'Debug'}}

>>> # Compared to flattened
>>> print(flattened)
{'name': 'my-config', 'generator': 'Ninja', 'binaryDir': '${sourceDir}/build/${presetName}', 'cacheVariables': {'CMAKE_BUILD_TYPE': 'Debug'}}

>>> # Get flattened preset with "pseudo" resolved macros
>>> resolved = presets.resolve_macro_values(CONFIGURE, "my-config")
>>> print(resolved)
{'name': 'my-config', 'generator': 'Ninja', 'binaryDir': '/home/user/project/build/my-config', 'cacheVariables': {'CMAKE_BUILD_TYPE': 'Debug'}}


>>> # Clean up test environment (important to avoid resource leaks)
>>> patcher.__exit__(None, None, None)

```
