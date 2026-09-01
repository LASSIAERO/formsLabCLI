#!/usr/bin/env python3
"""The `fconsole` entry point: a tab-switching REPL over the lab hardware.

Previously bootstrapped by `setenv.setup_environment()`, which inserted five
directories onto `sys.path` and chdir'd into the FORMS checkout. `formslab` is
an installed package now, so imports resolve on their own and the console runs
from any working directory.
"""
import os
import sys
import io
from contextlib import redirect_stdout

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from rich import print
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from formslab.console import style
from formslab.state import ensure_runtime_files
from formslab.console.sessions.base import CLIResult
from formslab.console.resources import handle_resources_command
from formslab.console.cmd_browser import handle_cmd_command
from formslab.console.console_help import build_command_index


def _make_factory(module_name: str, class_name: str):
    def _create():
        module = __import__(module_name, fromlist=[class_name])
        cls = getattr(module, class_name)
        return cls()
    return _create
# ─── Tab Configuration ─────────────────────────────────────
TAB_FACTORIES = {
    "ctrl": _make_factory("formslab.console.sessions.ctrl", "CtrlSession"),
    "cast": _make_factory("formslab.console.sessions.cast", "CastSession"),
    "log": _make_factory("formslab.console.sessions.log", "LogSession"),
    "psu": _make_factory("formslab.console.sessions.psu", "PSUSession"),
}
TABS = list(TAB_FACTORIES.keys())

active_sessions = {}
current_tab = "ctrl"
console = style.console


def clear_screen(
    *,
    console_obj=None,
    output=None,
    platform_name=None,
    system_call=None,
):
    """Clear one interactive screen without emitting controls to captures.

    Rich deliberately suppresses control codes when ``TERM=dumb``. That value
    can be inherited by a Windows launcher even though the attached console is
    interactive, leaving old dashboard text in place. Use ``cls`` for that
    specific Windows fallback; redirected output remains append-only.
    """
    console_obj = console_obj or console
    output = output or sys.stdout
    platform_name = platform_name or os.name
    system_call = system_call or os.system

    if not output.isatty():
        return
    if platform_name == "nt" and console_obj.is_dumb_terminal:
        system_call("cls")
        return
    if not console_obj.is_dumb_terminal:
        console_obj.clear()


def initial_tab_from_argv(argv):
    for arg in argv[1:]:
        if arg.startswith("--"):
            tab = arg.lstrip("-").lower()
            if tab in TABS:
                return tab
    return "ctrl"


def _make_unavailable_session(tab: str, exc: Exception):
    message = f"X {tab} tab unavailable: {exc}"

    class _UnavailableSession:
        def help(self):
            return CLIResult(content=Text(message, style=style.ERROR), suppress_prompt=True)

        def handle(self, _raw):
            return CLIResult(content=Text(message, style=style.ERROR))

        def prompt(self):
            return f"{tab}> "

    return _UnavailableSession()


def get_session(tab):
    if tab not in active_sessions:
        try:
            active_sessions[tab] = TAB_FACTORIES[tab]()
        except Exception as exc:
            active_sessions[tab] = _make_unavailable_session(tab, exc)
    return active_sessions[tab]

def render_tab_bar():
    bar = Text()
    for tab in TABS:
        if tab == current_tab:
            bar.append(f" {tab.upper()} ", style=f"bold white on {style.ACCENT1.color}")
        else:
            bar.append(f" {tab.upper()} ", style="white on grey15")
        bar.append(" ")
    return Panel(bar, style=style.BG, padding=(0,1))

def _strip_panel(renderable):
    """Remove Panel borders and replace with header text if present."""
    if isinstance(renderable, Panel):
        content = _strip_panel(renderable.renderable)
        header = None
        if renderable.title:
            title = renderable.title
            if not isinstance(title, Text):
                title = Text(str(title), style=style.HEADER)
            header = title
        if header:
            if isinstance(content, Group):
                return Group(header, *content.renderables)
            return Group(header, content)
        return content
    return renderable

def render_output(*renderables):
    clear_screen()
    console.print(render_tab_bar())
    valid = [r for r in renderables if r is not None]
    if not valid:
        valid = [Text("Ready.", style=style.TEXT)]
    for r in valid:
        console.print(_strip_panel(r))

def capture_stdout(func, *args, **kwargs):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        func(*args, **kwargs)
    return Text(buffer.getvalue(), style=style.TEXT)

def main():
    global current_tab
    # The CTRL command table and CAST device state are regenerated from code
    # defaults when absent. `setenv.setup_environment()` used to do this at
    # import; an installed console does it on the way into the REPL instead.
    ensure_runtime_files()

    current_tab = initial_tab_from_argv(sys.argv)
    session = get_session(current_tab)

    # ─── Initial help ───────────────────────────────────────
    initial_res = session.help()                # returns CLIResult
    render_output(initial_res.content)          # unwrap its .content

    while True:
        try:
            raw = console.input(session.prompt()).strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not raw:
            continue

        parts = raw.split()
        cmd = parts[0].lower()

        # ─── Exit ──────────────────────────────────────────
        if cmd in ("--resources", "resources"):
            res = handle_resources_command(raw)
            render_output(res.content)
            continue

        if cmd in ("--cmd", "cmd", "--tree", "tree"):
            mapped = raw
            if cmd in ("--tree", "tree"):
                mapped = ("cmd " + " ".join(parts[1:])).strip()
            res = handle_cmd_command(mapped)
            render_output(res.content)
            continue

        if cmd in ("--exit", "exit", "quit"):
            break

        # ─── Help ──────────────────────────────────────────
        if cmd in ("--help", "help"):
            if len(parts) > 1 and parts[1].lower() in ("cmd", "commands", "all"):
                help_res = build_command_index(TAB_FACTORIES, get_session)
                render_output(help_res.content)
                continue
            help_res = session.help()
            render_output(help_res.content)
            continue

        # ─── Tab switch ────────────────────────────────────
        if cmd in tuple(f"--{name}" for name in TABS):
            tab = cmd.lstrip("-")
            if tab in TABS:
                current_tab = tab
                session = get_session(current_tab)
                help_res = session.help()
                render_output(help_res.content)
            else:
                render_output(Text(f"✗ Unknown tab: {tab}", style=style.ERROR))
            continue

        # ─── Actual command dispatch ────────────────────────
        try:
            result = session.handle(raw)
        except Exception as exc:
            result = CLIResult(
                Text(f"✗ {current_tab.upper()} error: {exc}", style=style.ERROR)
            )

        # ─── Unwrap CLIResult ───────────────────────────────
        if isinstance(result, CLIResult):
            render_output(result.content)

        # ─── String ──────────────────────────────────────────
        elif isinstance(result, str):
            render_output(Text(result.strip(), style=style.TEXT))

        # ─── Nothing ─────────────────────────────────────────
        elif result is None:
            render_output(None)

        # ─── Rich renderable (Text/Panel/Group) ────────────
        else:
            render_output(result)

if __name__ == "__main__":
    main()
