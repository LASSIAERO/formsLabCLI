"""
Deprecated alias for :class:`lab.CryoBoard.CryoBoard`.

The name dates from when the Pico was thought of as the device rather than as
the USB-I2C bridge in front of the cryocooler board. Nothing in the tree
imports it; it is kept only so an operator's saved snippet still resolves, and
should be deleted once that is no longer a concern.
"""

from formslab.devices.CryoBoard import CryoBoard


PicoBoard = CryoBoard
