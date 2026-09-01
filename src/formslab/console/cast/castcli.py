from pathlib import Path
import json, time

from rich.text import Text
from rich.table import Table
from rich.console import Group
from rich.columns import Columns

from formslab.console.sessions.base import CLIResult
from formslab.console.cast.castutils import WriteCommand, GenerateCleanCast
from formslab.console.style import (
    TEXT, HEADER, ERROR, NUMBER, ACCENT1, ACCENT2, PROMPT_SUFFIX,
    DIM, INFO, LABEL, UNIT, STATE_ON, STATE_OFF, STATE_ERR, SUCCESS, WARNING,
)
from formslab.state import CAST_STATE_PATH

CASTPATH = CAST_STATE_PATH
HELPPATH = Path(__file__).parent / "casthelp.json"

# ── Display order for status_panel ───────────────────────────
# PSU1 and PSU2 are rendered side-by-side; remaining blocks follow
# in this fixed order.
_DISPLAY_ORDER = ["psu1", "psu2", "slta", "tvac", "cryo"]

# ── Helpers ──────────────────────────────────────────────────

def _load_cast() -> dict:
    """Read and validate castfile.json. Raises on failure."""
    raw = CASTPATH.read_text()
    data = json.loads(raw)
    if not isinstance(data, dict) or not data:
        raise ValueError("empty or invalid")
    return data

def _ago(ts_epoch: float) -> str:
    """Human-readable 'Xm Ys ago' from a unix timestamp."""
    dt = time.time() - ts_epoch
    if dt < 0:
        return "just now"
    if dt < 60:
        return f"{int(dt)}s ago"
    if dt < 3600:
        return f"{int(dt // 60)}m {int(dt % 60)}s ago"
    return f"{int(dt // 3600)}h {int((dt % 3600) // 60)}m ago"

# ── Help Panel ───────────────────────────────────────────────

def load_help():
    try:
        return json.loads(HELPPATH.read_text())
    except Exception:
        return {}

def help_panel() -> CLIResult:
    helps = load_help()
    result = Text()
    result.append("CAST Commands\n", HEADER)
    result.append("─" * 56 + "\n\n", DIM)

    maxlen = max((len(k) for k in helps), default=0) + 4
    for cmd, desc in helps.items():
        result.append(f"  --{cmd.ljust(maxlen)}", LABEL)
        result.append(f"{desc}\n", TEXT)

    return CLIResult(result, clear=True, suppress_prompt=True)

# ── Status Renderers ─────────────────────────────────────────

def _render_psu(name: str, entry: dict) -> Text:
    """Render a single PSU block (compact, for side-by-side layout)."""
    result = Text()
    ts_val = entry.get("timestamp", 0)
    ts_ago = _ago(ts_val) if ts_val else "unknown"

    result.append(f"{name.upper()}", HEADER)
    result.append(f"  {ts_ago}\n", DIM)

    stats = entry.get("status", {}) or {}
    reqs = entry.get("request", {}) or {}

    channel_keys = sorted(
        [k for k in stats if k.isdigit() and isinstance(stats[k], dict)],
        key=lambda s: int(s),
    )

    if not channel_keys:
        result.append("(no channel data)\n", DIM)
        return result

    # Header row
    result.append("CH ", LABEL)
    result.append("Vset   ", LABEL)
    result.append("Iset   ", LABEL)
    result.append("Vmeas   ", LABEL)
    result.append("Imeas   ", LABEL)
    result.append("State\n", LABEL)
    result.append("─" * 44 + "\n", DIM)

    for ch in channel_keys:
        st = stats[ch]
        rq = reqs.get(ch, {}) if isinstance(reqs, dict) else {}
        rq = rq or {}
        on = st.get("on", False)

        def _fmt_val(v, fmt, width):
            if v is None:
                result.append(f"{'---':>{width}} ", DIM)
            else:
                result.append(f"{v:{fmt}}", NUMBER)

        result.append(f"{ch}  ", INFO)
        _fmt_val(st.get('vset'),  "5.2f", 5); result.append("V ", UNIT)
        _fmt_val(st.get('cset'),  "5.3f", 5); result.append("A ", UNIT)
        _fmt_val(st.get('vmeas'), "6.3f", 6); result.append("V ", UNIT)
        _fmt_val(st.get('cmeas'), "6.3f", 6); result.append("A ", UNIT)

        if on is None:
            result.append("ERR", STATE_ERR)
        elif on:
            result.append("ON", STATE_ON)
        else:
            result.append("OFF", STATE_OFF)

        # Pending request hint
        rv = rq.get("voltage")
        rc = rq.get("current")
        if rv is not None or rc is not None:
            result.append(" ← ", DIM)
            if rv is not None:
                result.append(f"{rv:.2f}", WARNING)
                result.append("V", UNIT)
            if rc is not None:
                if rv is not None:
                    result.append(" ", DIM)
                result.append(f"{rc:.3f}", WARNING)
                result.append("A", UNIT)

        result.append("\n")

    return result


def _render_tvac(name: str, entry: dict) -> Text:
    """Render TVAC block with temperature data."""
    result = Text()
    ts_val = entry.get("timestamp", 0)
    ts_ago = _ago(ts_val) if ts_val else "unknown"

    result.append(f"  {name.upper()}", HEADER)
    result.append(f"  {ts_ago}\n", DIM)

    stats = entry.get("status", {}) or {}
    if not stats:
        result.append("  (no status data)\n", DIM)
        return result

    # Shroud targets vs measured (targets as integer)
    tpy = stats.get("target PY Shroud")
    tmy = stats.get("target MY Shroud")
    pyst = stats.get("PYsT")
    myst = stats.get("MYsT")

    if tpy is not None or pyst is not None:
        result.append("  PY Shroud  ", LABEL)
        if pyst is not None:
            result.append(f"{pyst:.2f}", NUMBER)
            result.append(" K", UNIT)
        if tpy is not None:
            result.append("  target ", DIM)
            result.append(f"{int(tpy)}", WARNING)
            result.append(" K", UNIT)
        result.append("\n")

    if tmy is not None or myst is not None:
        result.append("  MY Shroud  ", LABEL)
        if myst is not None:
            result.append(f"{myst:.2f}", NUMBER)
            result.append(" K", UNIT)
        if tmy is not None:
            result.append("  target ", DIM)
            result.append(f"{int(tmy)}", WARNING)
            result.append(" K", UNIT)
        result.append("\n")

    # PY/MY RTD lists
    pylist = stats.get("PYlist", [])
    mylist = stats.get("MYlist", [])
    if pylist:
        result.append("  PY RTDs    ", LABEL)
        for i, v in enumerate(pylist):
            if i > 0:
                result.append(", ", DIM)
            result.append(f"{v or 0:.2f}", NUMBER)
        result.append(" K\n", UNIT)
    if mylist:
        result.append("  MY RTDs    ", LABEL)
        for i, v in enumerate(mylist):
            if i > 0:
                result.append(", ", DIM)
            result.append(f"{v or 0:.2f}", NUMBER)
        result.append(" K\n", UNIT)

    # TC thermocouple grid (8 per row)
    tc = stats.get("TC08", [])
    if tc:
        result.append("  TC         ", LABEL)
        for i, v in enumerate(tc):
            if i > 0 and i % 8 == 0:
                result.append("\n             ", DIM)
            elif i > 0:
                result.append(" ", DIM)
            result.append(f"{v or 0:6.1f}", NUMBER)
        result.append(" K\n", UNIT)

    return result


def _render_generic(name: str, entry: dict) -> Text:
    """Render SLTA or other generic blocks as key: value pairs."""
    result = Text()
    ts_val = entry.get("timestamp", 0)
    ts_ago = _ago(ts_val) if ts_val else "unknown"

    result.append(f"  {name.upper()}", HEADER)
    result.append(f"  {ts_ago}\n", DIM)

    stats = entry.get("status", {}) or {}
    if not stats:
        result.append("  (no status data)\n", DIM)
        return result

    maxlen = max(len(str(k)) for k in stats) + 2
    for k, v in stats.items():
        if name.lower() == "slta" and str(k) == "CCON":
            continue
        result.append(f"  {str(k).ljust(maxlen)}", LABEL)
        if isinstance(v, bool):
            if v:
                result.append("ON", STATE_ON)
            else:
                result.append("OFF", STATE_OFF)
        elif isinstance(v, (int, float)):
            result.append(f"{v}", NUMBER)
        elif v is None:
            result.append("—", DIM)
        else:
            result.append(f"{v}", TEXT)
        result.append("\n")

    return result


# ── Status Panel (main entry) ────────────────────────────────

def status_panel(label: str = None) -> CLIResult:
    """Render styled status with PSU1/PSU2 side-by-side, then SLTA, then TVAC."""
    try:
        data = _load_cast()
    except FileNotFoundError:
        return CLIResult(Text("castfile.json not found — run --init to generate", style=ERROR), clear=True)
    except (json.JSONDecodeError, ValueError) as e:
        return CLIResult(Text(f"castfile.json is corrupted — run --init to regenerate\n({e})", style=ERROR), clear=True)
    except Exception as e:
        return CLIResult(Text(f"Error loading CAST data: {e}", style=ERROR), clear=True)

    # Single-label query: render just that block
    if label:
        lookup = {k.lower(): k for k in data}
        key = lookup.get(label.lower())
        if not key:
            return CLIResult(Text(f"No data for label: {label}", style=ERROR), clear=True)
        entry = data[key]
        if not isinstance(entry, dict):
            return CLIResult(Text(f"Invalid data for {label}", style=ERROR), clear=True)
        if key.lower().startswith("psu"):
            block = _render_psu(key, entry)
        elif key.lower() == "tvac":
            block = _render_tvac(key, entry)
        else:
            block = _render_generic(key, entry)
        return CLIResult(block, clear=True)

    # Full status: fixed layout order
    renderables = []

    # ── PSU1 + PSU2 side-by-side ─────────────────────────────
    psu_blocks = []
    for psu_name in ("psu1", "psu2"):
        entry = data.get(psu_name)
        if isinstance(entry, dict):
            psu_blocks.append(_render_psu(psu_name, entry))

    if psu_blocks:
        # Use a borderless table for side-by-side PSU columns
        tbl = Table.grid(padding=(0, 4))
        tbl.add_row(*psu_blocks)
        renderables.append(tbl)
        renderables.append(Text(""))  # spacer

    # ── Remaining blocks in fixed order ──────────────────────
    for block_name in _DISPLAY_ORDER:
        if block_name.startswith("psu"):
            continue  # already rendered above
        entry = data.get(block_name)
        if not isinstance(entry, dict):
            continue
        if block_name == "tvac":
            renderables.append(_render_tvac(block_name, entry))
        else:
            renderables.append(_render_generic(block_name, entry))
        renderables.append(Text(""))  # spacer

    # Any labels not in _DISPLAY_ORDER (future-proofing)
    for block_name, entry in data.items():
        if block_name in _DISPLAY_ORDER or not isinstance(entry, dict):
            continue
        renderables.append(_render_generic(block_name, entry))
        renderables.append(Text(""))

    return CLIResult(Group(*renderables), clear=True)


# ── Command Execution ────────────────────────────────────────

def _parse_bool(raw: str):
    """Parse ON/OFF/True/False/1/0. Returns bool or None."""
    val = raw.lower()
    if val in ("on", "true", "1"):
        return True
    if val in ("off", "false", "0"):
        return False
    return None


def _set_cryo_voltage(raw: str) -> CLIResult:
    try:
        voltage = float(raw)
    except ValueError:
        return CLIResult(Text("Invalid cryocooler voltage (must be a number)", style=ERROR))

    if not 12.0 <= voltage <= 20.0:
        return CLIResult(Text(f"Invalid CC voltage {voltage:.2f}. Allowed range: 12-20V.", style=ERROR))

    WriteCommand({"voltage": voltage}, "cryo")
    result = Text()
    result.append("✔ ", SUCCESS)
    result.append("Cryocooler board voltage → ", TEXT)
    result.append(f"{voltage:.2f}", NUMBER)
    result.append("V", UNIT)
    return CLIResult(result)


def _set_cryo_enabled(raw: str) -> CLIResult:
    enabled = _parse_bool(raw)
    if enabled is None:
        return CLIResult(Text("Invalid cryocooler state: use ON/OFF", style=ERROR))

    WriteCommand({"enabled": enabled}, "cryo")
    result = Text()
    result.append("✔ ", SUCCESS)
    result.append("Cryocooler → ", TEXT)
    if enabled:
        result.append("ON", STATE_ON)
    else:
        result.append("OFF", STATE_OFF)
    return CLIResult(result)


def _set_ccvres(raw: str) -> CLIResult:
    try:
        resistance = float(raw)
    except ValueError:
        return CLIResult(Text("Invalid CCVRES value (must be a number)", style=ERROR))

    if resistance < 62.0 or resistance > 1120.0:
        return CLIResult(Text(f"CCVRES {resistance:.1f} ohm out of range (62-1120)", style=ERROR))

    WriteCommand({"resistance": resistance}, "cryo")
    r = Text()
    r.append("✔ ", SUCCESS)
    r.append("CCVRES → ", TEXT)
    r.append(f"{resistance:.1f}", NUMBER)
    r.append(" ohm", UNIT)
    return CLIResult(r)

def execute_command(args: list[str]) -> CLIResult:
    if not args:
        return help_panel()

    cmd = args[0].lstrip("-").lower()

    try:
        if cmd == "help":
            return help_panel()

        if cmd == "init":
            GenerateCleanCast()
            r = Text()
            r.append("✔ ", SUCCESS)
            r.append("Clean castfile.json generated.", TEXT)
            return CLIResult(r, clear=True)

        # ── PSU2 per-channel control ─────────────────────────
        if cmd in ("psu2ch1", "psu2ch2"):
            ch = "1" if cmd == "psu2ch1" else "2"
            if len(args) < 2:
                return CLIResult(Text(f"Missing subcommand for --{cmd}. Use: on, off, set <V> <A>", style=ERROR))
            sub = args[1].lower()

            if sub == "on":
                WriteCommand({ch: {"on": True}}, "psu2")
                r = Text()
                r.append("✔ ", SUCCESS)
                r.append("PSU2 ", TEXT)
                r.append(f"CH{ch}", INFO)
                r.append(" → ", DIM)
                r.append("ON", STATE_ON)
                return CLIResult(r)
            elif sub == "off":
                WriteCommand({ch: {"on": False}}, "psu2")
                r = Text()
                r.append("✔ ", SUCCESS)
                r.append("PSU2 ", TEXT)
                r.append(f"CH{ch}", INFO)
                r.append(" → ", DIM)
                r.append("OFF", STATE_OFF)
                return CLIResult(r)
            elif sub == "set":
                if len(args) < 4:
                    return CLIResult(Text(f"Usage: --{cmd} set <voltage> <current>", style=ERROR))
                try:
                    v = float(args[2])
                    c = float(args[3])
                except ValueError:
                    return CLIResult(Text("Invalid voltage or current (must be numbers)", style=ERROR))
                if v < 0 or v > 32:
                    return CLIResult(Text(f"Voltage {v}V out of range (0-32V)", style=ERROR))
                if c < 0 or c > 3.2:
                    return CLIResult(Text(f"Current {c}A out of range (0-3.2A)", style=ERROR))
                WriteCommand({ch: {"voltage": v, "current": c}}, "psu2")
                r = Text()
                r.append("✔ ", SUCCESS)
                r.append("PSU2 ", TEXT)
                r.append(f"CH{ch}", INFO)
                r.append(" → ", DIM)
                r.append(f"{v:.2f}", NUMBER)
                r.append("V", UNIT)
                r.append(" @ ", DIM)
                r.append(f"{c:.3f}", NUMBER)
                r.append("A", UNIT)
                return CLIResult(r)
            else:
                return CLIResult(Text(f"Unknown subcommand '{sub}'. Use: on, off, set", style=ERROR))

        # ── Cryocooler control ───────────────────────────────
        if cmd == "ccvout":
            if len(args) < 2:
                return CLIResult(Text("Usage: --ccvout <12-20V>", style=ERROR))
            return _set_cryo_voltage(args[1])

        if cmd == "ccv":
            return CLIResult(Text("Use --ccvout <volts>", style=ERROR))

        if cmd == "ccout":
            if len(args) < 2:
                return CLIResult(Text("Usage: --ccout ON/OFF", style=ERROR))
            return _set_cryo_enabled(args[1])

        if cmd == "ccon":
            return CLIResult(Text("CCON is removed; use --ccout ON/OFF", style=ERROR))

        if cmd == "ccvres":
            if len(args) < 2:
                return CLIResult(Text("Usage: --ccvres <62-1120 ohms>", style=ERROR))
            return _set_ccvres(args[1])

        if cmd == "ccres":
            return CLIResult(Text("Use --ccvres <ohms>", style=ERROR))

        # ── Boolean toggles ──────────────────────────────────
        bool_map = {"sltarun": ("slta", "SLTARUN")}
        if cmd in bool_map:
            label, prop = bool_map[cmd]
            if len(args) < 2:
                return CLIResult(Text(f"Missing value for {cmd}", style=ERROR))
            b = _parse_bool(args[1])
            if b is None:
                return CLIResult(Text(f"Invalid value for {cmd}: must be ON/OFF", style=ERROR))
            WriteCommand({prop: b}, label)
            r = Text()
            r.append("✔ ", SUCCESS)
            r.append(f"{prop} → ", TEXT)
            if b:
                r.append("ON", STATE_ON)
            else:
                r.append("OFF", STATE_OFF)
            return CLIResult(r)

        # ── Status ───────────────────────────────────────────
        if cmd == "status":
            label = args[1] if len(args) > 1 else None
            return status_panel(label)

        # ── Lifecycle commands ───────────────────────────────
        if cmd in ("shutdown", "startup", "update"):
            if len(args) < 2:
                return CLIResult(Text(f"✗ Missing label. Usage: {cmd} <label>", style=ERROR))
            label = args[1].strip().lower()
            WriteCommand({cmd: True}, label)
            r = Text()
            r.append("✔ ", SUCCESS)
            r.append(f"{cmd.capitalize()} request → ", TEXT)
            r.append(f"[{label}]", INFO)
            return CLIResult(r)

        # ── SLTA imaging controls ────────────────────────────
        if cmd in ("force", "exposure", "idle", "nsamp", "clear"):
            force = any(a.lstrip("-").lower() == "force" for a in args)
            exposure = None
            idle = None
            nsamp = None
            clear_time = None
            autoExposure = any(a.lstrip("-").lower() == "auto" for a in args)
            it = iter(args)
            for a in it:
                a_stripped = a.lstrip("-").lower()
                if a_stripped == "exposure":
                    try:
                        nextVal = next(it, "600")
                        if nextVal.lower() == "auto":
                            autoExposure = True
                        else:
                            exposure = int(nextVal)
                            if exposure < 1 or exposure > 3600:
                                return CLIResult(Text(f"✗ Exposure {exposure}s out of range (1-3600s)", style=ERROR))
                    except ValueError:
                        return CLIResult(Text("✗ Invalid exposure value (must be integer or 'auto')", style=ERROR))
                elif a_stripped == "idle":
                    try:
                        idle = int(next(it, 30))
                        if idle < 1 or idle > 600:
                            return CLIResult(Text(f"✗ Idle {idle}s out of range (1-600s)", style=ERROR))
                    except ValueError:
                        return CLIResult(Text("✗ Invalid idle value (must be integer)", style=ERROR))
                elif a_stripped == "nsamp":
                    try:
                        nsamp = int(next(it, "1"))
                        if nsamp < 1 or nsamp > 1000:
                            return CLIResult(Text(f"✗ NSAMP {nsamp} out of range (1-1000)", style=ERROR))
                    except ValueError:
                        return CLIResult(Text("✗ Invalid nsamp value (must be integer)", style=ERROR))
                elif a_stripped == "clear":
                    try:
                        clear_time = int(next(it, "30"))
                        if clear_time < 0 or clear_time > 600:
                            return CLIResult(Text(f"✗ Clear {clear_time}s out of range (0-600s)", style=ERROR))
                    except ValueError:
                        return CLIResult(Text("✗ Invalid clear value (must be integer)", style=ERROR))

            req = {}
            if force:
                req["image"] = True
            if autoExposure:
                req["exposureAuto"] = True
            elif exposure is not None:
                req["exposure"] = exposure
            if idle is not None:
                req["idle"] = idle
            if nsamp is not None:
                req["nsamp"] = nsamp
            if clear_time is not None:
                req["clear"] = clear_time

            if not req:
                return CLIResult(Text("No valid CAST command provided.", style=ERROR))
            WriteCommand(req, "slta")

            r = Text()
            r.append("✔ ", SUCCESS)
            for i, (k, v) in enumerate(req.items()):
                if i > 0:
                    r.append(", ", DIM)
                if k == "image":
                    r.append("image capture", TEXT)
                elif k == "exposureAuto":
                    r.append("exposure", LABEL)
                    r.append("=", DIM)
                    r.append("auto", INFO)
                else:
                    r.append(f"{k}", LABEL)
                    r.append("=", DIM)
                    r.append(f"{v}", NUMBER)
            return CLIResult(r)

        # ── Image directory ──────────────────────────────────
        if cmd == "imagedir":
            if len(args) < 2:
                return CLIResult(Text("✗ Missing directory name. Usage: imagedir <dirname>", style=ERROR))
            dirname = args[1]
            if " " in dirname:
                return CLIResult(Text("✗ IMAGEDIR must be a single string with no spaces (or use 'default')", style=ERROR))
            WriteCommand({"IMAGEDIR": dirname}, "slta")
            r = Text()
            r.append("✔ ", SUCCESS)
            r.append("IMAGEDIR → ", TEXT)
            r.append(dirname, INFO)
            return CLIResult(r)

        # ── Shroud temperature ───────────────────────────────
        if cmd == "shroud":
            if len(args) < 3:
                return CLIResult(Text("✗ Usage: shroud <PY|MY> <K>", style=ERROR))
            arg_stripped = args[1].lstrip("-").upper()
            if arg_stripped not in ("PY", "MY"):
                return CLIResult(Text("✗ Invalid argument: must be PY or MY", style=ERROR))
            try:
                val = float(args[2])
            except ValueError:
                return CLIResult(Text("✗ Invalid temperature value (must be number)", style=ERROR))
            if val < 77 or val > 400:
                return CLIResult(Text(f"✗ Temperature {val}K out of safe range (77-400K)", style=ERROR))

            WriteCommand({arg_stripped: val}, "tvac")
            r = Text()
            r.append("✔ ", SUCCESS)
            r.append(f"{arg_stripped} shroud → ", TEXT)
            r.append(f"{val:.1f}", NUMBER)
            r.append(" K", UNIT)
            return CLIResult(r)

        # ── SLTA version ─────────────────────────────────────
        if cmd == "sltaversion":
            if len(args) < 2:
                return CLIResult(Text("✗ Usage: --sltaversion v1|v2", style=ERROR))
            ver = args[1].lower()
            if ver not in ("v1", "v2"):
                return CLIResult(Text(f"✗ Invalid version '{ver}'. Must be v1 or v2.", style=ERROR))
            WriteCommand({"version": ver}, "slta")
            r = Text()
            r.append("✔ ", SUCCESS)
            r.append("SLTA version → ", TEXT)
            r.append(ver, INFO)
            return CLIResult(r)

        return CLIResult(Text(f"✗ Unknown command: {' '.join(args)}. Type 'help' for available commands.", style=ERROR))

    except Exception as e:
        return CLIResult(Text(f"✗ CAST error: {e}", style=ERROR))
