"""Keep tkinter when a restricted build cannot run PyInstaller's Tcl probe.

The spec explicitly bundles Tcl/Tk scripts. Standard _tkinter binary discovery
and its runtime hook still run; packaged validation must verify both.
"""


def pre_find_module_path(_hook_api):
    pass
