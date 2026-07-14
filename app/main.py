import os
import re
import time
import uuid

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, Query, Header, HTTPException
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

app = FastAPI()

_state = {"csv_content": "", "current_filename": "", "session_id": str(uuid.uuid4())}
_langflow_api_key = None


class ChatRequest(BaseModel):
    instruction: str


def _get_or_create_api_key():
    token_resp = requests.post(
        f"{LANGFLOW_URL}/api/v1/login",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"username": LANGFLOW_USER, "password": LANGFLOW_PASS},
        timeout=15,
    )
    token_resp.raise_for_status()
    token = token_resp.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    keys_resp = requests.get(f"{LANGFLOW_URL}/api/v1/api_key/", headers=auth, timeout=10)
    keys_resp.raise_for_status()

    for key in keys_resp.json().get("api_keys", []):
        if key["name"] == "csv-editor-client" and key["is_active"]:
            full_key = key.get("api_key", "")
            if full_key and not full_key.endswith("*"):
                return full_key

    create_resp = requests.post(
        f"{LANGFLOW_URL}/api/v1/api_key/",
        headers={**auth, "Content-Type": "application/json"},
        json={"name": "csv-editor-client"},
        timeout=10,
    )
    create_resp.raise_for_status()
    return create_resp.json()["api_key"]


def ensure_api_key():
    if LANGFLOW_API_KEY:
        return LANGFLOW_API_KEY
    if not LANGFLOW_PASS:
        raise RuntimeError("Set LANGFLOW_API_KEY or LANGFLOW_SUPERUSER_PASSWORD")
    return _get_or_create_api_key()


def _get_langflow_api_key():
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
            resp = requests.get(
                f"{OPENRAG_URL}/v1/tasks/{task_id}",
                headers={"X-API-KEY": OPENRAG_API_KEY},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            status = (data.get("status") or "").lower()
            if status == "completed":
                return True, data
            if status == "failed":
                return False, data
        except Exception:
            pass
        time.sleep(poll_interval)
        elapsed += poll_interval
    return False, None


def extract_csv(text):
    text = text.replace("</br>", "").replace("<br>", "")
    text = text.replace("\\n", "\n")
    match = re.search(r"```[^\n]*\n(.*?)```", text, re.DOTALL)
    if match:
        lines = [l for l in match.group(1).split("\n") if l.strip()]
        return "\n".join(lines)
    return None


def chat_completion(csv_content, instruction, session_id):
    if not LANGFLOW_FLOW_ID:
        raise RuntimeError("LANGFLOW_CHAT_FLOW_ID is not set")

    api_key = _get_langflow_api_key()

    if csv_content:
        prompt = f"Current CSV:\n```\n{csv_content}\n```\n\nInstruction: {instruction}"
    else:
        prompt = instruction

    resp = requests.post(
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
    resp = requests.post(
        f"{OPENRAG_URL}/router/upload_ingest",
        headers={"X-API-KEY": OPENRAG_API_KEY},
        files={"file": (filename, file_obj)},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json().get("task_id")


# ---- /documents ----

@app.get("/documents")
def get_documents():
    try:
        docs = [{**doc, "status": "ingested"} for doc in list_ingested_documents()]
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"documents": docs}


@app.post("/documents", status_code=202)
async def upload_document(file: UploadFile, wait: bool = Query(False)):
    if not OPENRAG_API_KEY:
        raise HTTPException(status_code=500, detail="OPENRAG_API_KEY is not set")

    filename = os.path.basename(file.filename)
    try:
        task_id = _upload_and_ingest(filename, file.file)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    if not task_id:
        return {"filename": filename, "task_id": None, "status": "uploaded"}

    if wait:
        completed, task_data = wait_for_task(task_id)
        status = "completed" if completed else (task_data or {}).get("status", "unknown")
        if not completed:
            raise HTTPException(status_code=502, detail={"filename": filename, "task_id": task_id, "status": status})
        return {"filename": filename, "task_id": task_id, "status": status}

    return {"filename": filename, "task_id": task_id, "status": "processing"}

@app.delete("/documents/{filename}")
def delete_document(filename: str):
    if not OPENRAG_API_KEY:
        raise HTTPException(status_code=500, detail="OPENRAG_API_KEY is not set")

    resp = requests.delete(
        f"{OPENRAG_URL}/v1/documents",
        headers={"X-API-KEY": OPENRAG_API_KEY, "Content-Type": "application/json"},
        json={"filename": filename},
        timeout=30,
    )
    data = resp.json()

    if not data.get("success"):
        raise HTTPException(status_code=404, detail=data.get("error") or "unknown error")

    return {"filename": filename, "deleted_chunks": data.get("deleted_chunks", 0), "success": True}


# ---- /csv ----

@app.get("/csv")
def get_csv(accept: str | None = Header(None)):
    if not _state["csv_content"]:
        raise HTTPException(status_code=404, detail="no CSV loaded")

    if accept and "text/csv" in accept:
        return PlainTextResponse(
            _state["csv_content"],
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{_state["current_filename"] or "export.csv"}"'},
        )
    return {"filename": _state["current_filename"], "content": _state["csv_content"]}


@app.post("/csv/upload")
async def upload_csv(file: UploadFile):
    filename = os.path.basename(file.filename)
    content = (await file.read()).decode("utf-8").strip()

    _state["csv_content"] = content
    _state["current_filename"] = filename
    return {"filename": filename, "content": content}


@app.delete("/csv", status_code=204)
def delete_csv():
    _state["csv_content"] = ""
    _state["current_filename"] = ""


# ---- /chat ----

@app.post("/chat")
def post_chat(body: ChatRequest):
    try:
        response = chat_completion(_state["csv_content"], body.instruction, _state["session_id"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    new_csv = extract_csv(response)
    if new_csv:
        _state["csv_content"] = new_csv
    return {"response": response, "csv": new_csv}


@app.delete("/chat", status_code=204)
def delete_chat():
    _state["session_id"] = str(uuid.uuid4())
