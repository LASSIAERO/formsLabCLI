from formslab.console.sessions.base import ConsoleSession
from formslab.console.log import logcli
from formslab.console import style

class LogSession(ConsoleSession):
    def __init__(self):
        super().__init__("log", logcli.execute_command)

    def help(self):
        return logcli.help_panel()

    def banner(self):
        from rich.text import Text
        return Text("📜 LOG tab ready. Type --help for commands.", style=style.TEXT)

    def prompt(self):
        from formslab.console.style import ACCENT1, PROMPT_SUFFIX
        return f"[bold {ACCENT1.color}]log{PROMPT_SUFFIX} [/] "

