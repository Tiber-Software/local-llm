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
    match = re.search(r"```[^\n]*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
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

def main():
    api_key = ensure_api_key()
    
    while True:
        try:
            instruction = Prompt.ask("\n[bold]Instruction[/bold]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Closing application...[/dim]")
            break

        cmd = instruction.strip().lower()

        if cmd in ("quit", "exit", "q"):
            break
if __name__ == '__main__':
    main()