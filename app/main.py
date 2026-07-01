import csv
import io
import os
import re
import requests
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

_script_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_script_dir)
load_dotenv(os.path.join(_root_dir, ".env"))

console = Console()
LANGFLOW_URL = os.getenv("LANGFLOW_URL", "http://localhost:7860")
LANGFLOW_FLOW_ID = os.getenv("LANGFLOW_CHAT_FLOW_ID", "")
LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY", "")
LANGFLOW_USER = os.getenv("LANGFLOW_SUPERUSER", "admin")
LANGFLOW_PASS = os.getenv("LANGFLOW_SUPERUSER_PASSWORD", "")

def _get_or_create_api_key():
    # Get access token from langflow
    token_resp = requests.post(
        f"{LANGFLOW_URL}/api/v1/login",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"username": LANGFLOW_USER, "password": LANGFLOW_PASS},
        timeout=15
    )
    token_resp.raise_for_status()
    token = token_resp.json()['access_token']
    auth = {"Authorization": f"Bearer {token}"}

    # Get the api key from langflow if one already exists
    keys_resp = requests.get(f"{LANGFLOW_URL}/api/v1/api_key/", headers=auth, timeout=10)
    keys_resp.raise_for_status()

    for key in keys_resp.json().get("api_keys", []):
        if key["name"] == "csv-editor-client" and key["is_active"]:
            full_key = key.get("api_key", "")
            if full_key and not full_key.endswith("*"):
                return full_key

    # If no api key exists already, create one
    create_resp = requests.post(
        f"{LANGFLOW_URL}/api/v1/api_key/",
        headers={**auth, "Content-Type": "application/json"},
        json={"name": "csv-editor-client"},
        timeout=10
    )
    create_resp.raise_for_status()
    return create_resp.json()["api_key"]

def ensure_api_key():
    # Return the api key if one is set
    if LANGFLOW_API_KEY:
        return LANGFLOW_API_KEY
    if not LANGFLOW_PASS:
        console.print("[red]Error:[/red] Set LANGFLOW_API_KEY or LANGFLOW_SUPERUSER_PASSWORD")
        sys.exit(1)
    
    # Get/create an api key with the superuser password
    with console.status("[dim]Authenticating with Langflow...[/dim]"):
        return _get_or_create_api_key()

def extract_csv(text):
    text = text.replace("</br>", "").replace("<br>", "")
    text = text.replace("\\n", "\n")
    match = re.search(r"```[^\n]*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    stripped = text.strip()
    if "," in stripped and "\n" in stripped:
        return stripped

    return None

def render_csv(csv_text, title=""):
    reader = csv.reader(io.StringIO(csv_text))
    rows = [r for r in reader if any(c.strip() for c in r)]
    table = Table(title=title, show_header=bool(rows), header_style="bold cyan")
    
    if not rows:
        return table
    
    for col in rows[0]:
        table.add_column(col.strip())
    for row in rows[1:]:
        table.add_row(*[c.strip() for c in row])

    return table

def chat(api_key, csv_content, instruction):
    if not LANGFLOW_FLOW_ID:
        raise ValueError("LANGFLOW_CHAT_FLOW_ID is not set")

    if csv_content:
        prompt = f"Current CSV:\n```\n{csv_content}\n```\n\nInstruction: {instruction}"
    else:
        prompt = instruction
    
    resp = requests.post(
        f"{LANGFLOW_URL}/api/v1/run/{LANGFLOW_FLOW_ID}",
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        json={"input_value": prompt, "output_type": "chat", "input_type": "chat"},
        timeout=120
    )
    resp.raise_for_status()
    for output in resp.json().get("outputs", []):
        for inner in output.get("outputs", []):
            for msg in inner.get("messages", []):
                return msg.get("message", "")
    
    return ""

def main():
    console.print(Panel("[bold cyan] CSV Editor[/bold cyan] - type [bold]help[/bold] for commands", expand=False))

    api_key = ensure_api_key()
    csv_content=""
    current_filename=""

    if len(sys.argv) > 1:
        path = sys.argv[1]
        with open(path) as fin:
            csv_content = fin.read().strip()
        current_filename = os.path.basename(path)
        console.print(f"[green]Loaded[/green] {path}\n")
        console.print(render_csv(csv_content, title=current_filename))

    while True:
        try:
            instruction = Prompt.ask("\n[bold]Instruction[/bold]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Closing application...[/dim]")
            break

        cmd = instruction.strip().lower()

        if cmd in ("quit", "exit", "q"):
            break

        if cmd == "help":
            console.print(
                "   [cyan]show[/cyan]           - re-display current CSV as a table\n"
                "   [cyan]raw[/cyan]            - print raw CSV text\n"
                "   [cyan]save <path>[/cyan]    - save current CSV to a file\n"
                "   [cyan]quit[/cyan]           - exit"
            )
            continue

        if cmd == "show":
            console.print(render_csv(csv_content, title=current_filename or "CSV") if csv_content else "[dim]No CSV loaded yet[/dim]")
            continue

        if cmd.startswith("save "):
            path = instruction.strip()[5:].strip()
            with open(path, "w", newline="") as f:
                f.write(csv_content)
            console.print(f"[green]Saved[/green] -> {path}")
            continue
        
        with console.status("[yellow]Thinking...[/yellow]"):
            try:
                response = chat(api_key, csv_content, instruction)
            except Exception as e:
                console.print(f"[red]Error:[/red] {e}")
                continue
        
        new_csv = extract_csv(response)
        if new_csv:
            csv_content = new_csv
            console.print(render_csv(csv_content, title="Updated CSV"))
        else:
            console.print(Panel(response, title="Response"))

if __name__ == '__main__':
    main()