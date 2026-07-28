import csv
import io
import os
import re
import subprocess
import sys

import requests
from rich.console import Console
from rich.measure import Measurement
from rich.pager import Pager
from rich.table import Table

API_URL = os.getenv("API_URL", "http://localhost:3000")

console = Console()


def _clean_path(raw):
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        raw = raw[1:-1]
    return os.path.expanduser(raw)


_MEASURE_CAP = 100_000  # bounds worst-case cost if a single cell is huge;
                        # for normal CSVs the measured width is just the
                        # real sum of each column's content width


class _LessPager(Pager):
    """Pipe Rich's rendered output through `less -S -R` for horizontal scroll.

    -S: chop long lines instead of wrapping -> arrow keys scroll sideways.
    -R: pass through ANSI color codes.
    """

    def show(self, content: str) -> None:
        # Deliberately not subprocess.run(): its KeyboardInterrupt handling
        # calls process.kill() (SIGKILL), which cuts `less` off before it can
        # restore the terminal (raw mode / alternate screen), leaving the
        # terminal broken. Mirrors CPython's own pydoc.pipe_pager, which
        # works around the exact same subprocess.run behavior.
        try:
            proc = subprocess.Popen(["less", "-S", "-R"], stdin=subprocess.PIPE)
        except FileNotFoundError:
            console.print("[dim](less not found on PATH; showing table without paging)[/dim]")
            sys.stdout.write(content + "\n")
            return

        try:
            with proc.stdin as pipe:
                try:
                    pipe.write(content.encode())
                except (BrokenPipeError, KeyboardInterrupt):
                    pass
        except OSError:
            pass

        while True:
            try:
                proc.wait()
                break
            except KeyboardInterrupt:
                pass  # let `less` handle ctrl-C itself; don't kill it


def _natural_width(table: Table) -> int:
    """Width the table needs if no column is shrunk to fit the terminal."""
    options = console.options.update(max_width=_MEASURE_CAP)
    return Measurement.get(console, options, table).maximum


def _print_table(table: Table) -> None:
    """Print `table` normally, or page it horizontally through `less -S -R`
    if its natural width exceeds the real terminal width."""
    width = _natural_width(table)
    can_page = console.is_terminal and sys.stdin.isatty()

    if width <= console.width or not can_page:
        console.print(table)
        return

    supports_color = console.color_system is not None
    wide_console = Console(
        width=width,
        force_terminal=True,
        no_color=not supports_color,
        color_system=console.color_system,
    )
    with wide_console.pager(pager=_LessPager(), styles=supports_color):
        wide_console.print(table)


def render_csv(content):
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        console.print("[dim](empty CSV)[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan")
    for col in rows[0]:
        table.add_column(col)
    for row in rows[1:]:
        table.add_row(*row)
    _print_table(table)


def show_csv():
    resp = requests.get(f"{API_URL}/csv")
    if resp.status_code == 404:
        console.print("[yellow]No CSV loaded.[/yellow]")
        return
    resp.raise_for_status()
    data = resp.json()
    console.print(f"[bold]{data['filename']}[/bold]")
    render_csv(data["content"])


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
    render_csv(data["content"])


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


def list_documents():
    resp = requests.get(f"{API_URL}/documents")
    resp.raise_for_status()
    docs = resp.json()["documents"]
    if not docs:
        console.print("[dim](no documents)[/dim]")
        return
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("filename")
    table.add_column("status")
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
        console.print(f"[red]{resp.text}[/red]")
        return
    data = resp.json()
    text = data["response"]
    if data.get("csv"):
        # The fenced block is already shown as a table below; drop it here
        # so the edit doesn't get printed twice.
        text = re.sub(r"```[^\n]*\n.*?```", "", text, flags=re.DOTALL).strip()
    if text:
        console.print(text)
    if data.get("csv"):
        render_csv(data["csv"])


HELP = """\
Commands:
  /show              show current CSV as a table
  /raw               show current CSV as raw text
  /load <path>       load a local CSV file as the active CSV
  /download <path>   download current CSV to a local path
  /clear             clear the loaded CSV
  /docs              list ingested documents
  /upload <path>     upload a local file for ingestion
  /remove <file>     remove an ingested document
  /newchat           reset chat context
  /help              show this message
  /quit              exit
Anything else is sent as a chat instruction.\
"""


def main():
    console.print(f"[bold]CSV Editor TUI[/bold] — connected to {API_URL}")
    console.print(HELP)

    while True:
        try:
            line = console.input("[bold cyan]> [/bold cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue

        try:
            if line in ("/quit", "/exit"):
                break
            elif line == "/help":
                console.print(HELP)
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
        except requests.RequestException as e:
            console.print(f"[red]Request failed: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    main()
