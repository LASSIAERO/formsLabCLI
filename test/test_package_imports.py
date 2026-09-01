"""Every module in the package imports, on a base install.

The extraction moved ~50 modules out of a tree that only worked because
`setenv.py` put five directories on `sys.path` and chdir'd into the FORMS
checkout. Nothing there was import-checked as a package, so this walks the whole
package and imports each module. It is the test that would have caught every
mistake in the move.

"Base install" means `pip install -e .` with no extras: no FORMS, no mpremote,
no Qt. A module that needs one of those must defer the import to call time.
"""

import importlib
import pkgutil
import unittest

import formslab

# Firmware, not a module. `devices/pico_board_control.py` is deployed onto the
# Raspberry Pi Pico and imports MicroPython's `machine`, which does not exist on
# the PC. It ships as package data; it is never imported here.
FIRMWARE = {"formslab.devices.pico_board_control"}

# Modules that legitimately need an extra, and the distribution that provides
# it. These are plotting and the Qt tab -- they import at module scope on
# purpose, because each is a script or a tab that is simply unavailable without
# its extra, and the console already renders an unbuildable tab as unavailable.
# The map is asserted in both directions below, so a module that becomes lazy
# has to be removed from here.
EXTRA_ONLY = {
    "formslab.console.analysis.analysiscli": "matplotlib",
    "formslab.console.sessions.analysis": "matplotlib",
    "formslab.devices.plot_temp": "matplotlib",
    "formslab.devices.ramp_time": "matplotlib",
}


def _all_modules():
    for info in pkgutil.walk_packages(formslab.__path__, prefix="formslab."):
        if info.name in FIRMWARE:
            continue
        yield info.name


class PackageImports(unittest.TestCase):

    def test_every_module_imports(self):
        found = sorted(_all_modules())
        self.assertGreater(len(found), 40,
                           "package walk found suspiciously few modules")
        for name in found:
            if name in EXTRA_ONLY:
                continue
            with self.subTest(module=name):
                importlib.import_module(name)

    def test_extra_only_modules_are_still_extra_only(self):
        """Keeps EXTRA_ONLY honest in both directions.

        Every module listed must actually fail for the named distribution -- if
        one is made lazy, or its extra gets installed into the base set, this
        says so instead of quietly exempting a module that no longer needs it.
        """
        for name, dist in EXTRA_ONLY.items():
            with self.subTest(module=name):
                try:
                    importlib.import_module(dist)
                except ModuleNotFoundError:
                    pass
                else:
                    self.skipTest(f"{dist} is installed; extras are in play")
                with self.assertRaises(ModuleNotFoundError):
                    importlib.import_module(name)

    def test_firmware_is_present_but_not_imported(self):
        """The Pico firmware must ship, and must not be importable on the PC."""
        from pathlib import Path

        firmware = (Path(formslab.__file__).parent / "devices"
                    / "pico_board_control.py")
        self.assertTrue(firmware.exists(), f"missing firmware: {firmware}")

    def test_entry_point_is_callable(self):
        from formslab.app import main
        self.assertTrue(callable(main))

    def test_console_tabs_construct(self):
        """Each tab the REPL offers can actually be built on a base install."""
        from formslab.app import TAB_FACTORIES

        for tab, factory in TAB_FACTORIES.items():
            with self.subTest(tab=tab):
                factory()


if __name__ == "__main__":
    unittest.main()
