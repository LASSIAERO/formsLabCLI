# --- Imports ---
import os
from pathlib import Path
from numpy import mean
from forms.utils.rScripts import (
    rTaskRegister, rTaskStart, rTaskRunning, rTaskStop, RScriptControl
)
from formslab.console.cast.castutils import ReadCommand, UpdateStatus
from formslab.devices.tvacutils import _init, _update_tvac
from formslab.devices.shroud import HeaterController
from forms.bricks.thermal.radiation import C2K
from formslab.state import CAST_STATE_PATH
# --- Constants ---
name = os.path.splitext(os.path.basename(__file__))[0]
CASTPATH = CAST_STATE_PATH
TVACLOG = Path(__file__).resolve().parent.parent / "lab" / "TVAC.json"
# --- Encapsulated State ---
class rGlobal:
    disable = False
    useInitialize = False
    useHold = False
    useTick = False
    TICK_INTERVAL = 3
    HOLD_INTERVAL = 5
rg = rGlobal()

# --- rScript Entry Point ---
def rScript(forms):
    global rg
    # === rScript Controls & CUstom Initializations ===
    if rg.disable: return
    else:pass
    try:
        r = RScriptControl(forms, name)
        if rg.useInitialize: r.initialize()
        if rg.useHold:       r.hold(seconds=rg.HOLD_INTERVAL)
        if rg.useTick:       r.tick(seconds=rg.TICK_INTERVAL)
        if r: return
        else: 
            if rg.useHold: rg.useHold = False 
    except Exception as e:
        forms.log(f"❌ RScriptControl exception: {e}", level="ERROR", component="rTVAC")
        return
