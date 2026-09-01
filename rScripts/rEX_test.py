# --- Imports ---
import os
from pathlib import Path
from time import time
from dataclasses import dataclass
from typing import Callable, List
from forms.utils.rScripts import (
    rTaskRegister, rTaskStart, rTaskRunning, rTaskStop, RScriptControl
)
from formslab.console.cast.castutils import WriteCommand
from formslab.state import CAST_STATE_PATH

# --- Constants ---
name = os.path.splitext(os.path.basename(__file__))[0]
CASTPATH = CAST_STATE_PATH
TVACLOG = Path(__file__).resolve().parent.parent / "lab" / "TVAC.json"

# --- Encapsulated State ---
class rGlobal:
    disable = False
    useInitialize = False
    useHold = True
    useTick = False
    TICK_INTERVAL = 3
    HOLD_INTERVAL = 10
    # timeline state
    initialized = False
    t0 = None
    timeline: List["Event"] = []
rg = rGlobal()

# --- Event type ---
@dataclass
class Event:
    at: float                      # absolute unix time (seconds)
    action: Callable[[], None]     # callback (no args)
    label: str                     # for logs
    done: bool = False

# --- rScript Entry Point ---
def rScript(forms):
    global rg

    # === rScript Controls & Custom Initializations ===
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
        forms.log(f"RScriptControl exception: {e}", level="ERROR", component="rTVAC")
        return

    # --- Build the timeline once (non-blocking scheduler) ---
    if not rg.initialized:
        rg.t0 = time()
        rg.timeline = []

        H = 3600  # seconds per hour

        # Helpers
        def after(dt_s: float, action: Callable[[], None], label: str):
            rg.timeline.append(Event(at=rg.t0 + dt_s, action=action, label=label))

        def cmd_psu2_vset(v: float):
            def _f():
                WriteCommand({"vset": v}, "psu2")
                forms.log(f"PSU2 vset -> {v} V", component="rTVAC")
            return _f

        def cmd_cc(on: bool):
            """Turn cryocooler ON/OFF and adjust record cadence accordingly."""
            def _f():
                WriteCommand({"enabled": bool(on)}, "cryo")
                forms.log(f"Cryocooler {'ON' if on else 'OFF'}", component="rTVAC")
                # Adjust record cadence in sync with CC state:
                if on:
                    forms.record(value=1, unit="seconds")   # high cadence during chill
                    forms.log("Record cadence set to 1 s (chilldown).", component="rTVAC")
                else:
                    forms.record(value=30, unit="seconds")  # relaxed cadence when OFF
                    forms.log("Record cadence set to 30 s (idle).", component="rTVAC")
            return _f

        def cmd_shroud(key: str, val: float):
            def _f():
                WriteCommand({key: val}, "tvac")
                forms.log(f"Shroud {key} set -> {val} K", component="rTVAC")
            return _f

        # ===================== Timeline ======================
        # Up front: set shrouds to 240 K and default record cadence to 30 s
        PYT = 290
        MYT = 290
        tEQ0 = 20 / H
        tCD = 30 / H 
        tEQ = 0 / H
        tRs = 2
        v1 = 12

        after(0, lambda: forms.record(value=tRs, unit="seconds"), f"Set record cadence = {tRs} s (baseline)")
        after(0, cmd_shroud("PY", PYT), f"Set PY shroud = {PYT} K")
        after(5, cmd_shroud("MY", MYT), f"Set MY shroud = {MYT} K")

        t = 0

        # Segment 1: wait 5h (Bring shroud to Equilibrium)
        t += tEQ0 * H
        after(t, cmd_psu2_vset(v1), f"Set PSU2 {v1}V - bring to EQ over {tEQ} hours - (Segment 1)")
        after(t, cmd_cc(True),      f"Chilldown for {tCD} hours - CC ON - (Segment 1)")
        t += tCD * H                  # <- chill 10 h
        after(t, cmd_cc(False),     "CC OFF (end Segment 1)")

        # Optional final dwell marker:
        t += tEQ * H
        after(t, lambda: forms.log(f"Final {tEQ}h dwell complete.", component="rTVAC"), "Final dwell")

        rg.initialized = True
        forms.log(f"Timeline start t0={rg.t0:.0f}, {len(rg.timeline)} events scheduled.", component="rTVAC")

    # --- Advance timeline: fire due events and return (non-blocking) ---
    now = time()
    for ev in rg.timeline:
        if not ev.done and now >= ev.at:
            try:
                ev.action()
                ev.done = True
                forms.log(f"Executed event: {ev.label}", component="rTVAC")
            except Exception as e:
                ev.done = True  # avoid hot-loop retry
                forms.log(f"Event '{ev.label}' failed: {e}", level="ERROR", component="rTVAC")

    return
