"""
Helpers for routing CryoBoard commands through the CAST `cryo` channel.

Other routines should not talk to the Pico board directly. They should
queue requests here and let `rCryoBoard` own the actual hardware access.
"""
from __future__ import annotations

from typing import Optional

from formslab.console.cast.castutils import WriteCommand
from formslab.devices.cryo_config import ccvres_ohms_from_code


def build_cryo_request(
    *,
    voltage: Optional[float] = None,
    resistance: Optional[float] = None,
    code: Optional[int] = None,
    enabled: Optional[bool] = None,
    startup: Optional[bool] = None,
    shutdown: Optional[bool] = None,
) -> dict:
    """Build a normalized CAST request for `rCryoBoard`."""
    request = {}

    if startup is not None:
        request["startup"] = bool(startup)
    if shutdown is not None:
        request["shutdown"] = bool(shutdown)
    if voltage is not None:
        request["voltage"] = round(float(voltage), 2)
    if resistance is not None:
        request["resistance"] = round(float(resistance), 2)
    if code is not None:
        request["resistance"] = ccvres_ohms_from_code(int(code))
    if enabled is not None:
        request["enabled"] = bool(enabled)

    return request


def queue_cryo_request(
    forms=None,
    *,
    component: str = "CRYO",
    voltage: Optional[float] = None,
    resistance: Optional[float] = None,
    code: Optional[int] = None,
    enabled: Optional[bool] = None,
    startup: Optional[bool] = None,
    shutdown: Optional[bool] = None,
) -> dict:
    """
    Queue a CryoBoard request via CAST and optionally log it.

    Returns the request dict that was written. Empty requests are ignored.
    """
    request = build_cryo_request(
        voltage=voltage,
        resistance=resistance,
        code=code,
        enabled=enabled,
        startup=startup,
        shutdown=shutdown,
    )
    if not request:
        return {}

    WriteCommand(request, "cryo")

    if forms is not None:
        parts = []
        if startup is True:
            parts.append("startup")
        if shutdown is True:
            parts.append("shutdown")
        if voltage is not None:
            parts.append(f"CCVOUT={float(voltage):.2f}V")
        if resistance is not None:
            parts.append(f"CCVRES={float(resistance):.1f}ohm")
        elif code is not None:
            ohms = ccvres_ohms_from_code(int(code))
            parts.append(f"CCVRES={ohms:.1f}ohm (#{int(code)})")
        if enabled is not None:
            parts.append(f"CCOUT={'ON' if enabled else 'OFF'}")
        forms.log(", ".join(parts), component=component)

    return request
