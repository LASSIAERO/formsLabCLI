# rSTATES.py
# --- Imports ---
import os
from pathlib import Path
from numpy import mean
from forms.utils.rScripts import (
    rTaskRegister, rTaskStart, rTaskRunning, rTaskStop, RScriptControl
)
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
    last_epoch = None
    last_mode_code = None
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
    rGCRS = forms.satellite.get_position()
    vGCRS = forms.satellite.get_velocity()
    # Use GCRS->ITRF conversion via FrameService
    # Convert Vector -> list to avoid numpy dtype=float conversion error
    rECEF, vECEF, _ = forms.frames.gcrf_to_itrf(
        rGCRS.to_list(), vGCRS.to_list(), forms.time.epoch
    )
    LLAdata = ECEF2GEO(rECEF[0],rECEF[1],rECEF[2])

    forms.get_variable('LATgd').set(deg(LLAdata[0]))
    forms.get_variable('LON').set(deg(LLAdata[1]))

    forms.get_variable('rECI').set(x=rGCRS[0],y=rGCRS[1],z=rGCRS[2])
    forms.get_variable('vECI').set(x=vGCRS[0],y=vGCRS[1],z=vGCRS[2])

    forms.get_variable('rECEF').set(x=rECEF[0],y=rECEF[1],z=rECEF[2])
    forms.get_variable('vECEF').set(x=vECEF[0],y=vECEF[1],z=vECEF[2])
    
    # --- Attitude Pointing (simplified ADCS) ---
    if hasattr(forms.satellite, 'adcs') and forms.satellite.adcs:
        try:
            # Mode selection based on eclipse state
            in_umbra = forms.satellite.InUmbra

            # Check if mode needs to change
            current_mode = forms.satellite.adcs.current_mode
            new_mode = 'radec' if in_umbra else 'sun'

            # Update pointing target if mode changed
            if current_mode != new_mode:
                if in_umbra:
                    # Science pointing in umbra (Galactic Center)
                    forms.satellite.adcs.point_to('radec',
                        ra=4.649557127312893, dec=-0.5061454830783556, body_axis=[1, 0, 0])
                    forms.log('Attitude: Galactic center pointing (+X)', level='INFO', component='rSTATES')
                else:
                    # Sun tracking for power
                    forms.satellite.adcs.point_to('sun', body_axis=[0, 0, 1])
                    forms.log('Attitude: Sun tracking (+Z)', level='INFO', component='rSTATES')

            # Step ADCS (propagates and updates FormTypes variables)
            forms.satellite.adcs.step()

        except Exception as e:
            forms.log(f"ADCS update failed: {e}", level="WARNING", component="rSTATES")
