import codecs
import csv
import io
import os
import re
import select
import sys
import termios
import tty
from dataclasses import dataclass

import requests
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.measure import Measurement
from rich.segment import Segment, SegmentLines
from rich.table import Table
from rich.text import Text

API_URL = os.getenv("API_URL", "http://localhost:3000")

console = Console()

_MEASURE_CAP = 100_000  # bounds worst-case cost if a single cell is huge;
                        # for normal CSVs the measured width is just the
                        # real sum of each column's content width

_MAX_TABLE_HEIGHT = 20
_SCROLL_STEP = 8
_KEY_POLL_TIMEOUT = 0.15
_ESCAPE_TIMEOUT = 0.03


def _clean_path(raw):
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        raw = raw[1:-1]
    return os.path.expanduser(raw)


def _natural_width(table: Table) -> int:
    """Width the table needs if no column is shrunk to fit the terminal."""
    options = console.options.update(max_width=_MEASURE_CAP)
    return Measurement.get(console, options, table).maximum


class _PinnedCSV:
    """State for the CSV table pinned above the input line during the
    interactive Live session."""

    def __init__(self):
        self.table = None
        self.filename = None
        self.row_count = 0
        self.col_count = 0
        self.offset = 0

    def set(self, table, row_count, col_count, filename=None):
        self.table = table
        self.filename = filename
        self.row_count = row_count
        self.col_count = col_count
        self.offset = 0

    def clear(self):
        self.table = None
        self.filename = None
        self.row_count = 0
        self.col_count = 0
        self.offset = 0


_pinned_csv = _PinnedCSV()
_live = None  # bound to the active Live instance only while _run_interactive runs
_busy = False  # True while a dispatched command is in flight (e.g. a slow /chat call)
_input_buffer = ""  # current text of the pinned input line, while _run_interactive runs


def _refresh_live():
    """Rebuild the pinned layout from current state and repaint immediately.

    This is the only path that should ever touch the screen while Live is
    active: Live.refresh() alone just repaints whatever renderable was last
    handed to it, so anything that changes _pinned_csv/_input_buffer/_busy
    must go through here, not call live.refresh()/live.update() directly.
    """
    if _live is not None:
        _live.update(_build_layout(_pinned_csv, _input_buffer), refresh=True)


def render_csv(content, filename=None):
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        if _live is not None:
            _pinned_csv.clear()
            _refresh_live()
        else:
            console.print("[dim]✗ empty CSV[/dim]")
        return

    table = Table(
        show_header=True,
        header_style="bold cyan",
        padding=(0, 1),
        border_style="bright_black",
    )
    for col in rows[0]:
        table.add_column(col)
    for row in rows[1:]:
        table.add_row(*row)

    if _live is not None:
        _pinned_csv.set(table, len(rows) - 1, len(rows[0]), filename=filename)
        _refresh_live()
    else:
        console.print(table)


def show_csv():
    resp = requests.get(f"{API_URL}/csv")
    if resp.status_code == 404:
        console.print("[yellow]No CSV loaded.[/yellow]")
        return
    resp.raise_for_status()
    data = resp.json()
    if _live is None:
        console.print(f"[bold]{data['filename']}[/bold]")
    render_csv(data["content"], filename=data["filename"])


def show_raw():
    resp = requests.get(f"{API_URL}/csv")
    if resp.status_code == 404:
        console.print("[yellow]No CSV loaded.[/yellow]")
        return
    resp.raise_for_status()
    console.print(resp.json()["content"])


def load_csv(path):
    path = _clean_path(path)
    if not os.path.exists(path):
        console.print(f"[red]{path} not found locally[/red]")
        return
    with open(path, "rb") as fin:
        resp = requests.post(f"{API_URL}/csv", files={"file": (os.path.basename(path), fin)})
    resp.raise_for_status()
    data = resp.json()
    console.print(f"[green]Loaded {data['filename']}[/green]")
    render_csv(data["content"], filename=data["filename"])


def download_csv(dest_path):
    dest_path = _clean_path(dest_path)
    resp = requests.get(f"{API_URL}/csv", headers={"Accept": "text/csv"})
    if resp.status_code == 404:
        console.print("[yellow]No CSV loaded.[/yellow]")
        return
    resp.raise_for_status()
    with open(dest_path, "wb") as fout:
        fout.write(resp.content)
    console.print(f"[green]Downloaded to {dest_path}[/green]")


def clear_csv():
    resp = requests.delete(f"{API_URL}/csv")
    resp.raise_for_status()
    console.print("[green]Cleared loaded CSV.[/green]")
    if _live is not None:
        _pinned_csv.clear()
        _refresh_live()


def list_documents():
    resp = requests.get(f"{API_URL}/documents")
    resp.raise_for_status()
    docs = resp.json()["documents"]
    if not docs:
        console.print("[dim]✗ no documents[/dim]")
        return
    table = Table(
        show_header=True,
        header_style="bold cyan",
        padding=(0, 1),
        border_style="bright_black",
    )
    table.add_column("filename")
    table.add_column("status", style="dim")
    for d in docs:
        table.add_row(d["filename"], d["status"])
    console.print(table)


def upload_document(path):
    path = _clean_path(path)
    if not os.path.exists(path):
        console.print(f"[red]{path} not found locally[/red]")
        return
    with open(path, "rb") as fin:
        resp = requests.post(f"{API_URL}/documents", files={"file": (os.path.basename(path), fin)})
    if resp.status_code >= 400:
        console.print(f"[red]Upload failed: {resp.text}[/red]")
        return
    console.print(f"[green]{resp.json()}[/green]")


def remove_document(filename):
    filename = _clean_path(filename)
    resp = requests.delete(f"{API_URL}/documents/{filename}")
    if resp.status_code >= 400:
        console.print(f"[red]Remove failed: {resp.text}[/red]")
        return
    console.print(f"[green]Removed {filename}[/green]")


def reset_chat():
    resp = requests.delete(f"{API_URL}/chat")
    resp.raise_for_status()
    console.print("[green]Chat context reset.[/green]")


def send_chat(instruction):
    resp = requests.post(f"{API_URL}/chat", json={"instruction": instruction})
    if resp.status_code >= 400:
        console.print(f"[red]✗ Error: {resp.text}[/red]")
        return
    data = resp.json()
    text = data["response"]
    if data.get("csv"):
        # The fenced block is already shown as a table below; drop it here
        # so the edit doesn't get printed twice.
        text = re.sub(r"```[^\n]*\n.*?```", "", text, flags=re.DOTALL).strip()
    if text:
        console.print(f"\n[cyan]Assistant:[/cyan]\n{text}\n")
    if data.get("csv"):
        render_csv(data["csv"])


def _build_help_table():
    """Build a nicely formatted help table."""
    table = Table(
        show_header=False,
        show_edge=False,
        padding=(0, 2),
        collapse_padding=True,
    )
    table.add_column(style="bold cyan")
    table.add_column(style="white")

    table.add_row("/show", "show current CSV as a table")
    table.add_row("/raw", "show current CSV as raw text")
    table.add_row("/load <path>", "load a local CSV file as the active CSV")
    table.add_row("/download <path>", "download current CSV to a local path")
    table.add_row("/clear", "clear the loaded CSV")
    table.add_row("/docs", "list ingested documents")
    table.add_row("/upload <path>", "upload a local file for ingestion")
    table.add_row("/remove <file>", "remove an ingested document")
    table.add_row("/newchat", "reset chat context")
    table.add_row("/help", "show this message")
    table.add_row("/quit", "exit")
    return table


def _dispatch(line):
    if line in ("/quit", "/exit"):
        return False
    elif line == "/help":
        console.print("\nCommands:")
        console.print(_build_help_table())
        console.print("Anything else is sent as a chat instruction.\n")
    elif line == "/show":
        show_csv()
    elif line == "/raw":
        show_raw()
    elif line.startswith("/load "):
        load_csv(line[len("/load "):])
    elif line.startswith("/download "):
        download_csv(line[len("/download "):])
    elif line == "/clear":
        clear_csv()
    elif line == "/docs":
        list_documents()
    elif line.startswith("/upload "):
        upload_document(line[len("/upload "):])
    elif line.startswith("/remove "):
        remove_document(line[len("/remove "):])
    elif line == "/newchat":
        reset_chat()
    elif line.startswith("/"):
        console.print(f"[red]Unknown command: {line}[/red]")
    else:
        send_chat(line)
    return True


def _run_line_mode():
    console.print(f"[bold]CSV Editor TUI[/bold] — connected to {API_URL}")
    console.print("[dim]Type /help for commands  •  Ctrl+D to quit[/dim]\n", highlight=False)

    while True:
        try:
            line = console.input("[bold cyan]> [/bold cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue

        try:
            if not _dispatch(line):
                break
        except requests.RequestException as e:
            console.print(f"[red]Request failed: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


# ---------------------------------------------------------------------------
# Interactive (TTY) mode: pinned CSV pane + persistent input line via Live.
# ---------------------------------------------------------------------------


@dataclass
class Key:
    kind: str  # CHAR, ENTER, BACKSPACE, CTRL_C, CTRL_D, LEFT, RIGHT, UP, DOWN
    char: str = ""


class _KeyReader:
    """Reads single keystrokes (including arrow-key escape sequences) off a
    raw-mode fd without blocking forever, so idle refresh/resize still runs."""

    _FINAL_BYTES = {b"A": "UP", b"B": "DOWN", b"C": "RIGHT", b"D": "LEFT"}

    def __init__(self, fd):
        self.fd = fd
        self._decoder = codecs.getincrementaldecoder("utf-8")()

    def _read_byte(self, timeout):
        r, _, _ = select.select([self.fd], [], [], timeout)
        if not r:
            return None
        data = os.read(self.fd, 1)
        return data or None

    def read_key(self):
        """Poll for one key, waiting up to _KEY_POLL_TIMEOUT. Returns None on
        no input (caller should treat this as an idle tick)."""
        b = self._read_byte(_KEY_POLL_TIMEOUT)
        if b is None:
            return None
        if b == b"\x1b":
            return self._read_escape()
        if b in (b"\r", b"\n"):
            return Key("ENTER")
        if b in (b"\x7f", b"\x08"):
            return Key("BACKSPACE")
        if b == b"\x03":
            return Key("CTRL_C")
        if b == b"\x04":
            return Key("CTRL_D")
        ch = self._decoder.decode(b)
        return Key("CHAR", ch) if ch else None

    def _read_escape(self):
        b = self._read_byte(_ESCAPE_TIMEOUT)
        if b is None or b != b"[":
            return None  # bare ESC or unsupported sequence: no-op

        seq = b""
        for _ in range(8):  # bounded so a stalled/unrecognized sequence can't hang input
            b = self._read_byte(_ESCAPE_TIMEOUT)
            if b is None:
                return None
            seq += b
            if 0x40 <= b[0] <= 0x7E:
                break

        kind = self._FINAL_BYTES.get(seq[-1:])
        return Key(kind) if kind else None


class _RawMode:
    def __init__(self, fd):
        self.fd = fd
        self._saved = None

    def __enter__(self):
        self._saved = termios.tcgetattr(self.fd)
        tty.setraw(self.fd)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._saved is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self._saved)
        return False


def _clamp_offset(offset, natural_width, width):
    max_offset = max(0, natural_width - width)
    return max(0, min(offset, max_offset))


def _render_table_window(pinned, width, max_height):
    if pinned.table is None:
        return Text("↳ no CSV loaded — /load <path> or /show", style="dim")

    natural_width = _natural_width(pinned.table)
    render_width = max(natural_width, width, 1)

    wide_console = Console(
        file=io.StringIO(),
        width=render_width,
        force_terminal=True,
        color_system=console.color_system,
    )
    lines = wide_console.render_lines(
        pinned.table,
        wide_console.options.update(width=render_width),
        pad=True,
    )

    max_rows = max(1, min(len(lines), max_height))
    lines = lines[:max_rows]

    pinned.offset = _clamp_offset(pinned.offset, natural_width, width)
    offset = pinned.offset

    cropped = []
    for line in lines:
        padded = Segment.adjust_line_length(line, render_width)
        parts = list(Segment.divide(padded, [offset, offset + width]))
        middle = parts[1] if len(parts) > 1 else []
        cropped.append(list(middle))

    return SegmentLines(cropped, new_lines=True)


def _render_status_line(pinned, width):
    if _busy:
        return Text("⟳ working…", style="yellow bold", overflow="crop", no_wrap=True)

    if pinned.table is None:
        hint = Text("← → scroll   ↑ ↓ history   Ctrl+D quit", style="dim")
        return hint

    natural_width = _natural_width(pinned.table)
    visible_start = pinned.offset
    visible_end = min(natural_width, pinned.offset + width)
    text = Text(overflow="crop", no_wrap=True)
    text.append(pinned.filename or "(unnamed)", style="bold")
    text.append(f"  •  {pinned.row_count} rows × {pinned.col_count} cols  ", style="dim")
    text.append(f"cols {visible_start}–{visible_end}/{natural_width}  ", style="dim")
    text.append("← → scroll   ↑ ↓ history   Ctrl+D quit", style="dim")
    return text


def _render_input_line(buffer, width):
    prompt = "❯ "
    avail = max(1, width - len(prompt) - 1)  # reserve 1 cell for the cursor glyph
    visible = buffer[-avail:] if len(buffer) > avail else buffer
    text = Text(no_wrap=True, overflow="crop")
    text.append(prompt, style="bold cyan")
    text.append(visible, style="white")
    text.append("▌", style="reverse")
    return text


def _build_layout(pinned, buffer):
    term_w = console.size.width
    term_h = console.size.height
    max_table_rows = max(5, term_h - 4)

    layout = Layout(name="root")
    layout.split_column(
        Layout(name="table"),
        Layout(name="status", size=1),
        Layout(name="input", size=1),
    )
    table_content = _render_table_window(pinned, term_w, max_table_rows)
    layout["table"].update(table_content)
    layout["status"].update(_render_status_line(pinned, term_w))
    layout["input"].update(_render_input_line(buffer, term_w))
    return layout


def _run_interactive():
    console.print(f"[bold]CSV Editor TUI[/bold] — connected to {API_URL}")
    console.print("[dim]Type /help for commands  •  Ctrl+D to quit[/dim]\n", highlight=False)

    try:
        show_csv()
    except Exception:
        pass

    console.print()
    while True:
        try:
            line = console.input("[bold cyan]> [/bold cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue

        try:
            if not _dispatch(line):
                break
        except requests.RequestException as e:
            console.print(f"[red]✗ Request failed: {e}[/red]")
        except Exception as e:
            console.print(f"[red]✗ Error: {e}[/red]")


def main():
    if sys.stdin.isatty() and sys.stdout.isatty():
        _run_interactive()
    else:
        _run_line_mode()


if __name__ == "__main__":
    main()
