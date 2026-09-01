
from forms.core.forms import FORMS
from forms.utils.rScripts import rScripts, eScript
from forms.bricks.propagation.state_equation import canonical_state_equation
import numpy as np

def initialize():
    forms = FORMS()
    mu = forms.planet.mu
    # --- UTC Timestamp ---
    timestamp = '2025:05:21:08:07:0.7980'
    # --- TLE Setup & Time Initialization ---
    dt = 1
    # tle = """           
    #     1 25544U 98067A   26026.56234843  .00012665  00000+0  24389-3 0  9999
    #     2 25544  51.6321 280.6014 0011114  32.6655 327.5019 15.48203655549808
    # """
    # forms.load_tle(tle)

    forms.load_koe(a=7000, e=0.001, i=51.6, raan=0.0, aop=0.0, ta=0.0,
                   mu=mu, timestamp=timestamp)

    # print('satellite initial state:', forms.satellite.get_state())
    # --- Time Span & Propagation Mode ---
    forms.time.set_span(mode="simulated", duration=190, units="minutes")
    # --- Propagator ---
    propagator = forms.satellite.set_propagator('rk45')
    # Bind state equation and params (only needed for RK-based propagators)
    forms.satellite.set_state_equation(canonical_state_equation)
    propagator.set_params({})

    propagator.bind(forms)
    propagator.initialize()
    propagator.simulated(fixed_dt=dt)

    # ========== ADCS CONFIGURATION ==========
    adcs_config = {
        # Inertia properties
        'J': np.array([[0.1804, 0, -0.0070],
                      [0, 0.1263, -0.0004],
                      [-0.0070, -0.0004, 0.1462]]),
        'J_w': 0.0000324 * np.eye(4),
        'L': 0.5 * np.array([[1, 1, -1, -1],
                            [-1, 1, 1, -1],
                            [np.sqrt(2), np.sqrt(2), np.sqrt(2), np.sqrt(2)]]),

        # Cryocooler (optional)
        'J_cc': 5.12e-06 * np.eye(3),
        'L_cc': np.eye(3),

        # Controller
        'controller': {
            'enabled': True,
            'k_p': 0.01,
            'k_d': 0.75,
        },

        # Initial state
        'initial_state': {
            'q': [0.6953, 0.1531, 0.1531, 0.6853],
            'omega': [0, 0, 0],
            'w_wheel': [0, 0, 0, 0],
            'w_cc': [0, 0, 0],
        },

        # Propagator settings
        'propagator': {
            'mode': 'simulated',
            'dt': dt,
        }
    }

    # Configure and initialize ADCS
    forms.satellite.set_adcs(adcs_config)
    forms.satellite.adcs.propagator.initialize()

    # Set initial pointing mode (Sun tracking)
    # Note: Mode switching handled by rSTATES_axionsat.py based on InUmbra flag
    forms.satellite.adcs.point_to('sun', body_axis=[0, 0, 1])

    # --- Logging ---
    print("Start Time (JD):", forms.time.epoch0)
    print("End Time   (JD):", forms.time.epoch1)

    # --- Routine Scripts ---
    rScripts(forms,[
        "rVARIABLES.py",
        "rSTATES_axionsat.py",
        "rFSS.py",
        "rFORCES.py",
        # "rVIS_attitude.py",
        # "rMEMORY.py",
        # "rTEST.py"
        ])
    eScript(forms)

    # --- Record ---
    forms.record(value=1,unit='seconds')
    return forms
