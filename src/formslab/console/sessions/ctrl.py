from formslab.console.sessions.base import ConsoleSession
from formslab.console.ctrl import ctrlcli

class CtrlSession(ConsoleSession):
    def __init__(self):
        super().__init__("ctrl", ctrlcli.execute_command)

    def help(self):
        return ctrlcli.help_panel()

    def banner(self):
        return ctrlcli.status_panel()
