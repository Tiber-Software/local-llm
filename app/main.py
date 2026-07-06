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

OPENRAG_URL = os.getenv("OPENRAG_URL", "http://openrag-backend:8000")
OPENRAG_API_KEY = os.getenv("OPENRAG_API_KEY", "")
DOCUMENTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents")
INGESTED_FILE = os.path.join(DOCUMENTS_DIR, ".ingested")

OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "opensearch")
OPENSEARCH_PORT = os.getenv("OPENSEARCH_PORT", "9200")
OPENSEARCH_USERNAME = os.getenv("OPENSEARCH_USERNAME", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "")
OPENSEARCH_INDEX_NAME = os.getenv("OPENSEARCH_INDEX_NAME", "documents")
OPENSEARCH_URL = f"https://{OPENSEARCH_HOST}:{OPENSEARCH_PORT}"

requests.packages.urllib3.disable_warnings()

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

def ingest():
    if not OPENRAG_API_KEY:
        console.print("[red]Error:[/red] OPENRAG_API_KEY is not set. Run [cyan]python3 scripts/generate-api-key.py[/cyan] and place in .env")
        return
    
    if not os.path.isdir(DOCUMENTS_DIR):
        console.print(f"[red]Error:[/red] documents/ directory not found at {DOCUMENTS_DIR}")

    ingested = set()
    if os.path.exists(INGESTED_FILE):
        with open(INGESTED_FILE) as fin:
            ingested = set(line.strip() for line in fin if line.strip())
    
    files = [f for f in os.listdir(DOCUMENTS_DIR) if not f.startswith(".") and f not in ingested]

    if not files:
        console.print("[dim]No new documents to ingest.[/dim]")
        return

    for filename in files:
        path = os.path.join(DOCUMENTS_DIR, filename)
        with console.status(f"[yellow]Ingesting {filename}...[/yellow]"):
            try:
                with open(path, "rb") as fin:
                    resp = requests.post(
                        f"{OPENRAG_URL}/router/upload_ingest",
                        headers={"X-API-KEY": OPENRAG_API_KEY},
                        files={"file": (filename, fin)},
                        timeout=300
                    )
                resp.raise_for_status()
                with open(INGESTED_FILE, 'a') as fout:
                    fout.write(filename + "\n")
                console.print(f"[green]Ingested[/green] {filename}")
            
            except Exception as e:
                console.print(f"[red]Failed[/red] {filename}: {e}")

def list_ingested_documents():
    resp = requests.post(
        f"{OPENSEARCH_URL}/{OPENSEARCH_INDEX_NAME}/_search",
        auth=(OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD),
        verify=False,
        json={
            "size": 0,
            "aggs": {
                "by_file": {
                    "terms": {"field": "filename", "size": 1000},
                    "aggs": {
                        "latest": {
                            "top_hits": {
                                "size": 1,
                                "sort": [{"indexed_time": {"order": "desc"}}],
                                "_source": ["connector_type", "mimetype", "indexed_time"]
                            }
                        }
                    }
                }
            }
        },
        timeout=15
    )
    resp.raise_for_status()

    buckets = resp.json().get("aggregations", {}).get("by_file", {}).get("buckets", [])
    docs = []
    for bucket in buckets:
        hits = bucket["latest"]["hits"]["hits"]
        source = hits[0]["_source"] if hits else {}
        docs.append({
            "filename": bucket["key"],
            "chunks": bucket["doc_count"],
            "source": source.get("connector_type", "-"),
            "mimetype": source.get("mimetype", "-"),
            "indexed_time": source.get("indexed_time", "-"),
        })

    return sorted(docs, key=lambda d: d["filename"].lower())

def extract_csv(text):
    text = text.replace("</br>", "").replace("<br>", "")
    text = text.replace("\\n", "\n")
    match = re.search(r"```[^\n]*\n(.*?)```", text, re.DOTALL)
    if match:
        lines = [l for l in match.group(1).split("\n") if l.strip()]
        return "\n".join(lines)

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
            # Langflow puts the final response in results.message.text
            text = inner.get("result", {}).get("message", {}).get("text", "")
            if text:
                return text
            
            # messages list contains intermediate tool-call steps
            machine_msgs = [m for m in inner.get("messages", []) if m.get("sender") == "Machine"]
            if machine_msgs:
                return machine_msgs[-1].get("message", "")
    
    return ""

def load(path):
    with open(path) as fin:
            csv_content = fin.read().strip()
    current_filename = os.path.basename(path)
    console.print(f"[green]Loaded[/green] {path}\n")
    console.print(render_csv(csv_content, title=current_filename))

    return current_filename, csv_content

def main():
    console.print(Panel("[bold cyan] CSV Editor[/bold cyan] - type [bold]help[/bold] for commands", expand=False))

    api_key = ensure_api_key()
    csv_content=""
    current_filename=""

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
                "   [cyan]save <file>[/cyan]    - save current CSV to a file\n"
                "   [cyan]quit[/cyan]           - exit\n"
                "   [cyan]ingest[/cyan]         - ingest any untracked documents in [cyan]documents/[/cyan]\n"
                "   [cyan]load <file>[/cyan]    - load a CSV into context\n"
                "   [cyan]csvs[/cyan]           - show available CSVs you can load\n"
                "   [cyan]docs[/cyan]           - list all ingested files\n"
                "   [cyan]clear[/cyan]          - clears the context"
            )
            continue

        if cmd == "show":
            console.print(render_csv(csv_content, title=current_filename or "CSV") if csv_content else "[dim]No CSV loaded yet[/dim]")
            continue

        if cmd == "csvs":
            csvs_dir = "/app/csvs"
            table = Table(title="CSVs", show_header=True, header_style="bold cyan")
            table.add_column("File")
            if os.path.isdir(csvs_dir):
                for f in sorted(os.listdir(csvs_dir)):
                    if not f.startswith("."):
                        table.add_row(f)
                
            console.print(table)
            continue
        
        if cmd == "docs":
            try:
                with console.status("[dim]Querying knowledge base...[/dim]"):
                    docs = list_ingested_documents()
            except Exception as e:
                console.print(f"[red]Error:[/red] could not reach knowledge base: {e}")
                continue

            table = Table(title="Ingested Documents", show_header=True, header_style="bold cyan")
            table.add_column("File")
            table.add_column("Source")
            table.add_column("Type")
            table.add_column("Chunks", justify="right")
            table.add_column("Indexed")
            if not docs:
                console.print("[dim]No documents found in the knowledge base.[/dim]")
                continue
            for d in docs:
                table.add_row(d["filename"], d["source"], d["mimetype"], str(d["chunks"]), d["indexed_time"])
            console.print(table)
            continue

        if cmd == "raw":
            console.print(csv_content if csv_content else "[dim]No CSV loaded yet[/dim]")
            continue

        if cmd == "clear":
            csv_content = ""
            current_filename = ""
            console.clear()
            console.print("[dim]Context cleared[/dim]")
            continue

        if cmd.startswith("load "):
            path = instruction.strip()[5:].strip()
            current_filename, csv_content = load(f"/app/csvs/{path}")
            continue
            

        if cmd.startswith("save "):
            path = instruction.strip()[5:].strip()
            filename = os.path.basename(path)

            # If they entered a path, warn them that it'll just be saved to the csvs dir
            if filename != path:
                console.print(f"[yellow]Warning:[/yellow] file will be saved at csvs/{filename}")

            with open(f"/app/csvs/{filename}", "w") as fout:
                fout.write(csv_content)
            console.print(f"[green]Saved[/green] -> csvs/{path}")
            continue

        if cmd == "ingest":
            ingest()
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