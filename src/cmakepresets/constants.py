from typing import Final

CONFIGURE: Final = "configure"
BUILD: Final = "build"
TEST: Final = "test"
PACKAGE: Final = "package"
WORKFLOW: Final = "workflow"

PRESET_TYPES = [CONFIGURE, BUILD, TEST, PACKAGE, WORKFLOW]

PRESET_MAP: Final = {
    CONFIGURE: "configurePresets",
    BUILD: "buildPresets",
    TEST: "testPresets",
    PACKAGE: "packagePresets",
    WORKFLOW: "workflowPresets",
}
