"""Test collection rules for the lab console.

Two groups are excluded from a plain `pytest` run, for two different reasons.

**Hardware.** These open a serial port, a VISA session or a camera, and hang or
fail on a machine with nothing plugged in. They are the drivers' real coverage
and they are run deliberately, at the bench, by naming the file:

    pytest test/test_DP832A.py

**Foreign runtime.** `test_smtcpi.py` imports `sm_tc`, a Raspberry-Pi-only
distribution, and `test_slta.py` chdir's into a path that exists on the sLTA
host. Neither can run here at all.

Carried over from the FORMS `conftest.py` quarantine at extraction, minus the
astrodynamics entries, which stayed with the library.
"""

collect_ignore = [
    # hardware -- needs instruments on the bench
    "test/test_CCboard.py",
    "test/test_DP832A.py",
    "test/test_RTD16.py",
    "test/test_SMTC08.py",
    "test/test_image.py",
    "test/test_psu_request_resilience.py",
    # foreign runtime -- Pi-only distribution / sLTA host paths
    "test/test_slta.py",
    "test/test_smtcpi.py",
]
