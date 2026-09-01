# formslab/console/sessions/base.py
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Optional
from rich.text import Text
from rich.panel import Panel

@dataclass
class CLIResult:
    content: Any  # Any Rich renderable (Text, Panel, Group, Table, Columns, ...)
    clear: bool = False
    suppress_prompt: bool = False
    # Optional structured channel carried alongside the rendered content. Used
    # by the apply gate to round-trip a serialized changeset through the
    # stateless GUI bridge (and, later, to render panels structurally in Zenith).
    data: Optional[dict] = None

class ConsoleSession(ABC):
    """Base class for a console tab session."""

    def __init__(self, name: str, handler: Callable[..., CLIResult]):
        self.name = name
        self._cli_handler = handler
        # Most handlers take only the parsed `parts`. A handler that opts into
        # the structured channel declares a `payload` parameter; we forward it
        # only to those, so existing handlers are untouched.
        self._handler_takes_payload = self._accepts_payload(handler)

    @staticmethod
    def _accepts_payload(handler: Callable[..., Any]) -> bool:
        try:
            return "payload" in inspect.signature(handler).parameters
        except (TypeError, ValueError):
            return False

    def handle(self, raw: str, payload: Optional[dict] = None) -> CLIResult:
        parts = raw.strip().split()
        if not parts:
            return CLIResult(content="")
        try:
            if self._handler_takes_payload:
                return self._cli_handler(parts, payload=payload)
            return self._cli_handler(parts)
        except Exception as e:
            return CLIResult(content=f"✗ {self.name.upper()} error: {e}")

    @abstractmethod
    def help(self):
        pass

    def banner(self):
        return None

    def prompt(self):
        return f"{self.name}> "
