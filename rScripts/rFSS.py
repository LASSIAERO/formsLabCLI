# --- Imports ---
import os
from pathlib import Path
from numpy import mean
from forms.utils.rScripts import (
    rTaskRegister, rTaskStart, rTaskRunning, rTaskStop, RScriptControl
)
from formslab.console.cast.castutils import ReadCommand, UpdateStatus
from forms.bricks.frames.transforms import ECEF2GEO, eci_to_body
from forms.bricks.math.units import deg
from forms.bricks.bodies.meeus import SPAlow, rSUNJ2000
from forms.bricks.constants import AUVSOP87KM
from formslab.state import CAST_STATE_PATH
# from forms.bricks.models.VSOP87.VSOP87utils import sun_geocentric_ecliptic_xyz

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
    # --- Main logic ---
    JDTT = forms.time.jdtt + forms.time.jdttfrac
    forms.get_variable('gmst').set(forms.planet.gmst(forms.time.JD))
    SPAlow_dict = SPAlow(forms.time.ttt)
    # SUN (Meeus direct from current ttt to avoid stale bindings)
    x_au, y_au, z_au = rSUNJ2000(SPAlow_dict)
    forms.get_variable('rSUNJ2000').set(
        x=x_au * AUVSOP87KM,
        y=y_au * AUVSOP87KM,
        z=z_au * AUVSOP87KM,
    )

    forms.get_variable('subLAT').set(SPAlow_dict['subLat'])
    forms.get_variable('subLON').set(SPAlow_dict['subLon'])
