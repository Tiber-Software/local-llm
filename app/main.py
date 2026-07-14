import os
import re
import time
import uuid

import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, UploadFile, Query, Header, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

_script_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_script_dir)
load_dotenv(os.path.join(_root_dir, ".env"))

LANGFLOW_URL = os.getenv("LANGFLOW_URL", "http://localhost:7860")
LANGFLOW_FLOW_ID = os.getenv("LANGFLOW_CHAT_FLOW_ID", "")
LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY", "")
LANGFLOW_USER = os.getenv("LANGFLOW_SUPERUSER", "admin")
LANGFLOW_PASS = os.getenv("LANGFLOW_SUPERUSER_PASSWORD", "")

OPENRAG_URL = os.getenv("OPENRAG_URL", "http://openrag-backend:8000")
OPENRAG_API_KEY = os.getenv("OPENRAG_API_KEY", "")

OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "opensearch")
OPENSEARCH_PORT = os.getenv("OPENSEARCH_PORT", "9200")
OPENSEARCH_USERNAME = os.getenv("OPENSEARCH_USERNAME", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "")
OPENSEARCH_INDEX_NAME = os.getenv("OPENSEARCH_INDEX_NAME", "documents")
OPENSEARCH_URL = f"https://{OPENSEARCH_HOST}:{OPENSEARCH_PORT}"

requests.packages.urllib3.disable_warnings()

app = FastAPI(
    title="csv-editor backend",
    description="REST API for loading a CSV, chatting with an LLM to edit it, "
    "and managing ingested documents via OpenRAG.",
    version="0.1.0",
)

_state = {"csv_content": "", "current_filename": "", "session_id": str(uuid.uuid4())}
_langflow_api_key = None

# Reused across requests for connection pooling; headers/auth that vary per-call
# are still passed explicitly to each request.
_langflow_session = requests.Session()
_openrag_session = requests.Session()
_openrag_session.headers.update({"X-API-KEY": OPENRAG_API_KEY})
_opensearch_session = requests.Session()
_opensearch_session.auth = (OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD)
_opensearch_session.verify = False


class ChatRequest(BaseModel):
    instruction: str


class DocumentInfo(BaseModel):
    filename: str
    chunks: int
    source: str
    mimetype: str
    indexed_time: str
    status: str


class DocumentsResponse(BaseModel):
    documents: list[DocumentInfo]


class DocumentTaskResponse(BaseModel):
    filename: str
    task_id: str | None
    status: str


class DocumentDeleteResponse(BaseModel):
    filename: str
    deleted_chunks: int
    success: bool


class CsvResponse(BaseModel):
    filename: str
    content: str


class ChatResponse(BaseModel):
    response: str
    csv: str | None


def require_openrag_key() -> None:
    """FastAPI dependency: 500s the request if OPENRAG_API_KEY isn't configured."""
    if not OPENRAG_API_KEY:
        raise HTTPException(status_code=500, detail="OPENRAG_API_KEY is not set")


def _upstream(fn, *args, **kwargs):
    """Run an upstream call, translating any failure into a 502."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


def _get_or_create_api_key():
    """Log into Langflow and return an active 'csv-editor-client' API key,
    creating one if it doesn't already exist. Always hits the network —
    callers wanting caching should go through _get_langflow_api_key()."""
    token_resp = _langflow_session.post(
        f"{LANGFLOW_URL}/api/v1/login",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"username": LANGFLOW_USER, "password": LANGFLOW_PASS},
        timeout=15,
    )
    token_resp.raise_for_status()
    token = token_resp.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    keys_resp = _langflow_session.get(f"{LANGFLOW_URL}/api/v1/api_key/", headers=auth, timeout=10)
    keys_resp.raise_for_status()

    for key in keys_resp.json().get("api_keys", []):
        if key["name"] == "csv-editor-client" and key["is_active"]:
            full_key = key.get("api_key", "")
            if full_key and not full_key.endswith("*"):
                return full_key

    create_resp = _langflow_session.post(
        f"{LANGFLOW_URL}/api/v1/api_key/",
        headers={**auth, "Content-Type": "application/json"},
        json={"name": "csv-editor-client"},
        timeout=10,
    )
    create_resp.raise_for_status()
    return create_resp.json()["api_key"]


def ensure_api_key():
    """Resolve which Langflow API key to use: the statically configured
    LANGFLOW_API_KEY if set (no network call), otherwise bootstrap one
    dynamically via _get_or_create_api_key() using the superuser password."""
    if LANGFLOW_API_KEY:
        return LANGFLOW_API_KEY
    if not LANGFLOW_PASS:
        raise RuntimeError("Set LANGFLOW_API_KEY or LANGFLOW_SUPERUSER_PASSWORD")
    return _get_or_create_api_key()


def _get_langflow_api_key():
    """Return the Langflow API key, resolving and caching it in the
    _langflow_api_key global on first call so ensure_api_key()'s work
    (a login + lookup/create round trip, in the dynamic case) only runs once
    per process instead of on every /chat request."""
    global _langflow_api_key
    if _langflow_api_key is None:
        _langflow_api_key = ensure_api_key()
    return _langflow_api_key


def wait_for_task(task_id, timeout=1000, poll_interval=2):
    """Poll OpenRAG's task-status endpoint until the ingestion task reaches
    a terminal state. The backend force-refreshes the OpenSearch index before
    marking a task COMPLETED, so this is a race-free readiness signal."""
    elapsed = 0
    while elapsed < timeout:
        try:
            resp = _openrag_session.get(f"{OPENRAG_URL}/v1/tasks/{task_id}", timeout=15)
            resp.raise_for_status()
            data = resp.json()
            status = (data.get("status") or "").lower()
            if status == "completed":
                return True, data
            if status == "failed":
                return False, data
        except requests.RequestException:
            pass
        time.sleep(poll_interval)
        elapsed += poll_interval
    return False, None


def extract_csv(text):
    """Pull the CSV body out of an LLM chat response.

    Expects the model to wrap its answer in a fenced code block (per
    scripts/system_prompt.txt); strips HTML-style line breaks the model
    sometimes emits instead of literal newlines. Returns None if no fenced
    block is found, meaning the response wasn't a CSV edit."""
    text = text.replace("</br>", "").replace("<br>", "")
    text = text.replace("\\n", "\n")
    match = re.search(r"```[^\n]*\n(.*?)```", text, re.DOTALL)
    if match:
        lines = [l for l in match.group(1).split("\n") if l.strip()]
        return "\n".join(lines)
    return None


def chat_completion(csv_content, instruction, session_id):
    """Send the current CSV (if any) plus the user's instruction to the
    Langflow chat flow and return the raw text of its reply. Does not parse
    out a CSV edit itself — callers run extract_csv() on the result."""
    if not LANGFLOW_FLOW_ID:
        raise RuntimeError("LANGFLOW_CHAT_FLOW_ID is not set")

    api_key = _get_langflow_api_key()

    if csv_content:
        prompt = f"Current CSV:\n```\n{csv_content}\n```\n\nInstruction: {instruction}"
    else:
        prompt = instruction

    resp = _langflow_session.post(
        f"{LANGFLOW_URL}/api/v1/run/{LANGFLOW_FLOW_ID}",
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        json={"input_value": prompt, "output_type": "chat", "input_type": "chat", "session_id": session_id},
        timeout=120,
    )
    resp.raise_for_status()
    for output in resp.json().get("outputs", []):
        for inner in output.get("outputs", []):
            text = inner.get("result", {}).get("message", {}).get("text", "")
            if text:
                return text
            machine_msgs = [m for m in inner.get("messages", []) if m.get("sender") == "Machine"]
            if machine_msgs:
                return machine_msgs[-1].get("message", "")
    return ""


def list_ingested_documents():
    """Query OpenSearch directly for one summary row per ingested filename
    (chunk count, source connector, mimetype, latest indexed_time). This is
    the sole source of truth for what's ingested — there's no separate
    tracking of ingestion state in this service."""
    resp = _opensearch_session.post(
        f"{OPENSEARCH_URL}/{OPENSEARCH_INDEX_NAME}/_search",
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
                                "_source": ["connector_type", "mimetype", "indexed_time"],
                            }
                        }
                    },
                }
            },
        },
        timeout=15,
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


def _upload_and_ingest(filename, file_obj):
    """Upload a file to OpenRAG's ingest endpoint and return its task_id
    (None if OpenRAG didn't hand back one, e.g. an unsupported file type)."""
    resp = _openrag_session.post(
        f"{OPENRAG_URL}/router/upload_ingest",
        files={"file": (filename, file_obj)},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json().get("task_id")


# ---- /documents ----

@app.get("/documents", response_model=DocumentsResponse, tags=["documents"])
def get_documents():
    """List every ingested document, as currently indexed in OpenSearch."""
    docs = [{**doc, "status": "ingested"} for doc in _upstream(list_ingested_documents)]
    return {"documents": docs}


@app.post(
    "/documents",
    status_code=202,
    dependencies=[Depends(require_openrag_key)],
    response_model=DocumentTaskResponse,
    tags=["documents"],
)
async def upload_document(file: UploadFile, wait: bool = Query(False)):
    """Upload and ingest a document via OpenRAG.

    By default returns immediately with the ingest task_id (status
    "processing"); pass ?wait=true to block until the task reaches a
    terminal state and get back its final status instead."""
    filename = os.path.basename(file.filename)
    task_id = _upstream(_upload_and_ingest, filename, file.file)

    if not task_id:
        return {"filename": filename, "task_id": None, "status": "uploaded"}

    if wait:
        completed, task_data = wait_for_task(task_id)
        status = "completed" if completed else (task_data or {}).get("status", "unknown")
        if not completed:
            raise HTTPException(status_code=502, detail={"filename": filename, "task_id": task_id, "status": status})
        return {"filename": filename, "task_id": task_id, "status": status}

    return {"filename": filename, "task_id": task_id, "status": "processing"}

@app.delete(
    "/documents/{filename}",
    dependencies=[Depends(require_openrag_key)],
    response_model=DocumentDeleteResponse,
    tags=["documents"],
)
def delete_document(filename: str):
    """Remove a document (and all its chunks) from OpenRAG by filename."""
    resp = _upstream(
        _openrag_session.delete,
        f"{OPENRAG_URL}/v1/documents",
        headers={"Content-Type": "application/json"},
        json={"filename": filename},
        timeout=30,
    )
    data = _upstream(resp.json)

    if not data.get("success"):
        raise HTTPException(status_code=404, detail=data.get("error") or "unknown error")

    return {"filename": filename, "deleted_chunks": data.get("deleted_chunks", 0), "success": True}


# ---- /csv ----

@app.get("/csv", response_model=CsvResponse, tags=["csv"])
def get_csv(accept: str | None = Header(None)):
    """Return the currently loaded CSV as JSON, or as a raw file download
    if the client sends 'Accept: text/csv'."""
    if not _state["csv_content"]:
        raise HTTPException(status_code=404, detail="no CSV loaded")

    if accept and "text/csv" in accept:
        return PlainTextResponse(
            _state["csv_content"],
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{_state["current_filename"] or "export.csv"}"'},
        )
    return {"filename": _state["current_filename"], "content": _state["csv_content"]}


@app.post("/csv", response_model=CsvResponse, tags=["csv"])
async def upload_csv(file: UploadFile):
    """Load a new CSV into server state, replacing whatever was loaded before."""
    filename = os.path.basename(file.filename)
    content = (await file.read()).decode("utf-8").strip()

    _state["csv_content"] = content
    _state["current_filename"] = filename
    return {"filename": filename, "content": content}


@app.delete("/csv", status_code=204, tags=["csv"])
def delete_csv():
    """Clear the loaded CSV only — leaves the chat session untouched, so
    chat history/context isn't lost just because the CSV was reset."""
    _state["csv_content"] = ""
    _state["current_filename"] = ""


# ---- /chat ----

@app.post("/chat", response_model=ChatResponse, tags=["chat"])
def post_chat(body: ChatRequest):
    """Send an instruction to the LLM against the current CSV. If the reply
    contains a fenced CSV block, it replaces the server's stored CSV state."""
    response = _upstream(chat_completion, _state["csv_content"], body.instruction, _state["session_id"])

    new_csv = extract_csv(response)
    if new_csv:
        _state["csv_content"] = new_csv
    return {"response": response, "csv": new_csv}


@app.delete("/chat", status_code=204, tags=["chat"])
def delete_chat():
    """Rotate the session_id, resetting Langflow chat memory/context only —
    leaves the loaded CSV untouched (mirrors delete_csv()'s decoupling)."""
    _state["session_id"] = str(uuid.uuid4())
