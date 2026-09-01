import json
from pathlib import Path
from importlib import import_module

from formslab.console.sessions.base import CLIResult
from rich.text import Text
from formslab.console.style import TEXT, ERROR

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QPlainTextEdit, QSizePolicy
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# Load command configuration
CONFIG_FILE = Path(__file__).resolve().parent / "analysisfile.json"
with open(CONFIG_FILE, 'r') as f:
    COMMANDS = json.load(f)


def help_panel() -> CLIResult:
    """
    Generate help text from COMMANDS config as CLIResult.
    """
    lines = ["ANALYSIS Commands:"]
    for cmd, info in COMMANDS.items():
        desc = info.get('desc', '')
        lines.append(f"  {cmd:<10} {desc}")
    return CLIResult(content=Text("\n".join(lines), style=TEXT), clear=False, suppress_prompt=True)


def execute_command(parts: list[str]) -> CLIResult:
    """
    Execute a configured command and return a CLIResult,
    attaching 'figure' attribute for plots if needed.
    """
    # Help request
    if not parts or parts[0].lower() in ('help', '--help'):
        return help_panel()

    cmd = parts[0]
    args = parts[1:]
    if cmd not in COMMANDS:
        return CLIResult(content=Text(f"Unknown command: {cmd}", style=ERROR))

    info = COMMANDS[cmd]
    script = info.get('script')
    if not script:
        return CLIResult(content=Text(f"No script configured for {cmd}", style=ERROR))

    # Load module
    try:
        module = import_module(script)
    except ModuleNotFoundError as e:
        return CLIResult(content=Text(f"Load error: {e}", style=ERROR))

    # Choose function: wrapper or function
    wrapper = info.get('wrapper')
    func_name = wrapper if not args and wrapper else info.get('function', 'main')

    # Get function
    try:
        func = getattr(module, func_name)
    except AttributeError as e:
        return CLIResult(content=Text(f"Load error: {e}", style=ERROR))

    # Run function
    try:
        result = func(*args)
    except Exception as e:
        return CLIResult(content=Text(f"Error running {cmd}: {e}", style=ERROR))

    # Format table for list of dicts
    if isinstance(result, list) and result and all(isinstance(r, dict) for r in result):
        rows = result
        headers = list(rows[0].keys())
        widths = {h: max(len(h), *(len(str(r.get(h, ''))) for r in rows)) for h in headers}
        header = " | ".join(h.ljust(widths[h]) for h in headers)
        sep = "-+-".join('-' * widths[h] for h in headers)
        lines = [header, sep] + [" | ".join(str(r.get(h, '')).ljust(widths[h]) for h in headers) for r in rows]
        return CLIResult(content=Text("\n".join(lines), style=TEXT))

    # Single dict
    if isinstance(result, dict):
        content = "\n".join(f"{k}: {v}" for k, v in result.items())
    else:
        content = str(result)

    # Plot handling
    if info.get('plot', False):
        try:
            plot_mod = import_module(info.get('plot_module', script + 'Plot'))
            plot_fn = getattr(plot_mod, info.get('plot_function', 'plot'))
            samples = result if isinstance(result, list) else [result]
            fig = plot_fn(samples)
            res = CLIResult(content=Text(content, style=TEXT))
            setattr(res, 'figure', fig)
            return res
        except Exception as e:
            return CLIResult(content=Text(f"Plot error: {e}", style=ERROR))

    # Text result
    return CLIResult(content=Text(content, style=TEXT))


class AnalysisTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        # Figure
        self.canvas = FigureCanvas(Figure())
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.canvas, stretch=3)
        # Text output
        self.text_output = QPlainTextEdit()
        self.text_output.setReadOnly(True)
        layout.addWidget(self.text_output, stretch=1)
        # Input
        self.input = QLineEdit()
        self.input.setPlaceholderText("analysis> ")
        self.input.returnPressed.connect(self.process_command)
        layout.addWidget(self.input)

    def process_command(self):
        raw = self.input.text().strip()
        self.input.clear()
        if not raw:
            return
        result = execute_command(raw.split())
        # Handle plot
        fig = getattr(result, 'figure', None)
        if fig:
            self.canvas.figure.clear()
            self.canvas.figure = fig
            self.canvas.draw()
        # Render content
        if isinstance(result.content, Text):
            text = result.content.plain
        else:
            text = str(result.content)
        self.text_output.setPlainText(text)
