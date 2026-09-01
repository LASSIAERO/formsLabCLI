# --- Imports ---
import os
from pathlib import Path
from time import time
from dataclasses import dataclass
from typing import Callable, List
from forms.utils.rScripts import RScriptControl
from formslab.console.cast.castutils import WriteCommand
from formslab.devices.cryoboard_utils import queue_cryo_request

# --- Constants ---
name = os.path.splitext(os.path.basename(__file__))[0]

# --- Encapsulated State ---
class rGlobal:
    disable = False
    useInitialize = False
    useHold = True
    useTick = False
    TICK_INTERVAL = 3
    HOLD_INTERVAL = 10
    initialized = False
    t0 = None
    timeline: List["Event"] = []
rg = rGlobal()

# --- Event type ---
@dataclass
class Event:
    at: float
    action: Callable[[], None]
    label: str
    done: bool = False

# --- rScript Entry Point ---
def rScript(forms):
    global rg

    if rg.disable:
        return
    try:
        r = RScriptControl(forms, name)
        if rg.useInitialize: r.initialize()
        if rg.useHold:       r.hold(seconds=rg.HOLD_INTERVAL)
        if rg.useTick:       r.tick(seconds=rg.TICK_INTERVAL)
        if r:
            return
        else:
            if rg.useHold:
                rg.useHold = False
    except Exception as e:
        forms.log(f"RScriptControl exception: {e}", level="ERROR", component=name)
        return

    # --- Build timeline once ---
    if not rg.initialized:
        rg.t0 = time()
        rg.timeline = []

        H = 3600  # seconds per hour

        # === Helpers ===
        def after(dt_s: float, action: Callable[[], None], label: str):
            rg.timeline.append(Event(at=rg.t0 + dt_s, action=action, label=label))

        def cmd_psu2(ch: int, v: float, c: float):
            """Set PSU2 channel voltage/current."""
            def _f():
                WriteCommand({str(ch): {"voltage": v, "current": c}}, "psu2")
                forms.log(f"PSU2 CH{ch} -> {v:.2f}V, {c:.3f}A", component=name)
            return _f

        def cmd_psu2_on(ch: int):
            """Turn PSU2 channel on."""
            def _f():
                WriteCommand({str(ch): {"on": True}}, "psu2")
                forms.log(f"PSU2 CH{ch} ON", component=name)
            return _f

        def cmd_psu2_off(ch: int):
            """Turn PSU2 channel off."""
            def _f():
                WriteCommand({str(ch): {"on": False}}, "psu2")
                forms.log(f"PSU2 CH{ch} OFF", component=name)
            return _f

        def cmd_cryo(*, voltage=None, enabled=None, startup=None):
            """Send cryocooler requests through rCryoBoard."""
            def _f():
                queue_cryo_request(
                    forms,
                    component=name,
                    voltage=voltage,
                    enabled=enabled,
                    startup=startup,
                )
            return _f

        def cmd_cryo_on():
            def _f():
                queue_cryo_request(forms, component=name, enabled=True)
                forms.record(value=1, unit="seconds")
                forms.log("Record cadence -> 1s", component=name)
            return _f

        def cmd_cryo_off():
            def _f():
                queue_cryo_request(forms, component=name, enabled=False)
                forms.record(value=30, unit="seconds")
                forms.log("Record cadence -> 30s", component=name)
            return _f

        def cmd_shroud(key: str, val: float):
            """Set shroud temperature (PY or MY)."""
            def _f():
                WriteCommand({key: val}, "tvac")
                forms.log(f"Shroud {key} -> {val} K", component=name)
            return _f

        # ===================== Timeline ======================
        # Up front: set shrouds to 240 K and default record cadence to 30 s
        PYT = 260
        MYT = 260
        tEQ0 = 1
        tCD = 3
        tWU = 3
        tR = 30
        CCV = 17
        t = 0
        after(t, lambda: forms.record(value=tR, unit="seconds"), f"Set record cadence = {tR} s (baseline)")
        after(t, cmd_shroud("PY", PYT), f"Set PY shroud = {PYT} K")
        after(t+5, cmd_shroud("MY", MYT), f"Set MY shroud = {MYT} K")
        
        # Example: SLTA heat source on CH1, cryocooler via rCryoBoard
        after(t+10, cmd_psu2(1, 12.0, 1.250), "SLTA 12V 1.25A")
        after(t+15, cmd_cryo(startup=True), "Cryo startup")
        after(t+20, cmd_cryo(voltage=CCV, enabled=False), "CC prepared")
        after(t+30, cmd_psu2_on(1), "SLTA ON - equilbrium set")
        t += tEQ0 * H
        after(tEQ0*H, cmd_cryo_on(), "CC ON - chilldown")
        t += tCD * H 
        after(t, cmd_cryo_off(), "CC OFF - warmup")
        t += tWU * H
        after(t, cmd_psu2_off(1), "SLTA OFF - Complete")

        rg.initialized = True
        forms.log(f"Timeline started, {len(rg.timeline)} events scheduled.", component=name)

    # --- Execute due events ---
    now = time()
    for ev in rg.timeline:
        if not ev.done and now >= ev.at:
            try:
                ev.action()
                ev.done = True
                forms.log(f"Executed: {ev.label}", component=name)
            except Exception as e:
                ev.done = True
                forms.log(f"Event '{ev.label}' failed: {e}", level="ERROR", component=name)

    return
