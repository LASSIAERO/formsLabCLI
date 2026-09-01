# cli/sessions/usb.py
from formslab.console.sessions.base import ConsoleSession
from formslab.console.usb import usbcli

class USBSession(ConsoleSession):
    def __init__(self):
        super().__init__("usb", usbcli.run_command)

    def help(self):
        return usbcli.help_panel()
