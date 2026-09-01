# formslab/console/sessions/psu.py

from formslab.console.sessions.base import ConsoleSession, CLIResult
from formslab.console.psu import psucli
from formslab.console.style import ERROR, SUCCESS
from rich.text import Text

class PSUSession(ConsoleSession):
    def __init__(self):
        super().__init__("psu", psucli.execute_command)
        self.psus = psucli.psus()
        self.active = next(iter(self.psus), "all")

    def help(self):
        return psucli.help_panel()

    def banner(self):
        return psucli.status_panel(self.psus)

    def prompt(self):
        return psucli.prompt(self.active)

    def handle(self, raw: str):
        parts = raw.strip().split()

        # no input: show help
        if not parts:
            return psucli.help_panel()

        # change active device (including powerswitch)
        if parts[0] == "--device" and len(parts) == 2:
            label = parts[1].lower()
            if label in (*self.psus.keys(), "all", "ps"):
                self.active = label
                return CLIResult(Text(f"✔ Active device: {label}", style=SUCCESS))
            return CLIResult(Text(f"✗ Unknown device: {label}", style=ERROR))

        # delegate all other commands, passing current target
        try:
            return psucli.execute_command(parts, target=self.active)
        except Exception as exc:
            return CLIResult(Text(f"✗ PSU error: {exc}", style=ERROR))
