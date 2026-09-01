# FormsLabCLI

A terminal console for benchtop lab hardware: Rigol programmable supplies, a
cryocooler control board reached over a Raspberry Pi Pico I2C bridge, RTD and
thermocouple readers, TVAC shroud heaters, a Digital Loggers PowerSwitch, and
the sLTA imaging chain.

It runs standalone. When [FORMS](https://github.com/phi-a/FORMS) — the
astrodynamics library — is also installed, three extra commands light up: the
API-catalog browser, the Book reader, and the external-resource registry.

```
pip install -e .          # a working lab console
fconsole                  # start it
```

## Tabs

| Tab | What it drives |
|---|---|
| `ctrl` | Sequence control: launch, pause, resume, end |
| `cast` | Live hardware status panel |
| `psu` | Rigol supplies and PowerSwitch outlets |
| `log` | Tail the run log |
| `book` | The FORMS Book — needs the `[forms]` extra |

Switch with `--psu`, `--cast`, … or start on one: `fconsole --psu`.

## Install

The base install is the console and the transports its drivers open — nothing
else. No numpy, no matplotlib, no astrodynamics library; driving a PSU needs
none of them, and that absence is why this package was split out of FORMS.

```
pip install -e .              # console + transports
pip install -e ".[pico]"      # + mpremote, to talk to the cryo board's Pico bridge
pip install -e ".[analysis]"  # + matplotlib/PyQt6 plotting
pip install -e ".[forms]"     # + FORMS, for the catalog/Book/resource commands
pip install -e ".[dev]"       # + pytest
```

## Layout

```
src/formslab/
├── app.py       the `fconsole` entry point: the REPL and its tab bar
├── bridge.py    the ONLY module allowed to import `forms`
├── state.py     CTRL command table and CAST device state
├── console/     the tabs, sessions, and command tables
└── devices/     one module per instrument, plus usbmap.json
```

### The FORMS seam

`formslab/bridge.py` is the single place this package names `forms`. Accessors
import at call time and raise `FormsUnavailable` when the library is absent, so
the console loads and runs on a machine that has only the transports installed;
a library-backed command reports that FORMS is missing instead of raising
through the REPL. `bridge.SURFACES` is the whole dependency — five read-only
reporting modules. `test/test_console_bridge.py` enforces both properties.

### Configuration and state

Nothing is written inside the installed package. Three locations, by what the
thing is:

| Location | Holds | Override |
|---|---|---|
| package | code, command tables, Pico firmware, shipped defaults | — |
| config | live `usbmap.json`, CTRL command table, CAST device state | `$FORMSLAB_CONFIG_DIR` (default `~/.formslab`) |
| output | logs, captured frames, temperature histories | `$FORMSLAB_OUTPUT_DIR` (default `<cwd>/outputs`) |

`usbmap.json` is the hardware map: instrument VISA addresses and USB VID/PIDs,
hub locations, the PowerSwitch host, and the cryo board's I2C pins and firmware
version. It differs per bench, so it ships as a default in
`src/formslab/defaults/` and is copied into the config directory the first time
a driver asks for it — edit the copy, and an upgrade will not overwrite it. The
PowerSwitch password is read from the environment variable named by its
`password_env` key, never stored in the file.

Point `$FORMSLAB_CONFIG_DIR` somewhere else to run a second bench from one
machine.

## Tests

```
pytest
```

Instrument tests are quarantined in `conftest.py` — they need hardware on the
bench and are run by naming the file (`pytest test/test_DP832A.py`). Everything
else runs against fakes and passes on a bare install with nothing plugged in.

## Status

Extracted from the FORMS repository, where this was `python/cli/` +
`python/lab/`. One thing is not yet reconnected, and it is marked in the source:
**`ctrl`'s `run` / `missions`** and **`log`'s tail** reach the sequence host and
the `.zen` mission library, which have not moved over yet. They report an empty
library rather than launching anything.

## Relationship to FORMS

FORMS is the astrodynamics library and Astrid is the agent built on it; this is
the lab tool that used to live in that repository. The dependency points one way
only — FORMS knows nothing about this package — and is optional in this
direction. A later release adds an `astrid-mcp` path so the console can reach
FORMS through the agent as well as directly.
