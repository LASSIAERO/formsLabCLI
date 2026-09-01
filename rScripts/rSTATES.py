# --- Imports ---
import os
from pathlib import Path
from numpy import mean
from forms.utils.rScripts import (
    rTaskRegister, rTaskStart, rTaskRunning, rTaskStop, RScriptControl
)
from forms.bricks.frames.teme import TEME2ECEF
from forms.bricks.frames.transforms import ECEF2GEO
from forms.bricks.math.units import deg
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
        forms.log(f"RScriptControl exception: {e}", level="ERROR", component="rTVAC")
        return
    # --- Main logic ---
    rTEME = forms.get_variable('rTEME')
    vTEME = forms.get_variable('rTEME')
    rGCRS = forms.satellite.get_position()
    vGCRS = forms.satellite.get_velocity()
    # For GCRS->ECEF use the IAU-2006 path: Coord(rGCRS, "GCRF").to("ITRF", at=forms.time.instant)
    rECEF,vECEF, = TEME2ECEF(rTEME,vTEME,forms.time.JD)
    LLAdata = ECEF2GEO(rECEF[0],rECEF[1],rECEF[2])

    forms.get_variable('LATgd').set(deg(LLAdata[0]))
    forms.get_variable('LON').set(deg(LLAdata[1]))

    forms.get_variable('rECI').set(x=rGCRS[0],y=rGCRS[1],z=rGCRS[2])
    forms.get_variable('vECI').set(x=vGCRS[0],y=vGCRS[1],z=vGCRS[2])

    forms.get_variable('rECEF').set(x=rECEF[0],y=rECEF[1],z=rECEF[2])
    forms.get_variable('vECEF').set(x=vECEF[0],y=vECEF[1],z=vECEF[2])
