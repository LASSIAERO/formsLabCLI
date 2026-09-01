Bench analysis scripts. Not part of the `formslab` package: each runs top to
bottom and opens a plot window, so importing one would do work rather than
define anything.

    python scripts/plot_temp.py outputs/TVAC.json
    python scripts/ramp_time.py outputs/TVAC.json

Both need the plotting extra: `pip install -e ".[analysis]"`.
