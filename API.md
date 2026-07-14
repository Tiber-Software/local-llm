# CSV Editor REST API

Base URL: `http://localhost:5000`

Any request that fails upstream (OpenRAG, Langflow, or OpenSearch) is returned as `502` with a `detail` string describing the failure.

## Documents

### `GET /documents`
List every ingested document currently indexed in OpenSearch.

Response:
```json
{
  "documents": [
    {
      "filename": "string",
      "chunks": 0,
      "source": "string",
      "mimetype": "string",
      "indexed_time": "string",
      "status": "string"
    }
  ]
}
```

### `POST /documents`
Upload and ingest a document via OpenRAG. By default returns immediately with the ingest `task_id` (status `processing`); pass `?wait=true` to block until the task reaches a terminal state and get its final status back instead.

Requires `OPENRAG_API_KEY` to be configured on the server — if it isn't, the request fails with `500`.

Request: `multipart/form-data`, one part named `file`, sent as an actual file part (not a plain form field) — if it isn't, the request fails with `422`. The server derives the stored filename from the part's filename; if the part is sent with an empty filename, the request fails with `502` (OpenRAG returns an internal error for this case).

Query params:
- `wait` (boolean, default `false`)

Response (`202`):
```json
{"filename": "string", "task_id": "string", "status": "string"}
```

If OpenRAG doesn't recognize the file type, it still accepts the upload and queues it with a normal `task_id` and `status` (`"processing"`, then `"completed"` once finished) — but the file is never actually indexed, so it will not show up later in `GET /documents`.

If `wait=true` and the task ends up `failed` or times out, the request fails with `502` and a body of the same shape (`filename`, `task_id`, `status`) in `detail`.

Note: OpenRAG may normalize the stored filename/mimetype during processing (e.g. a `.txt` upload can come back as `.md`) — the name a document is ingested under isn't guaranteed to match the name it was uploaded with. Check `GET /documents` for the actual indexed filename before calling `DELETE /documents/{filename}`.

### `DELETE /documents/{filename}`
Remove a document (and all its chunks) from OpenRAG by filename.

Requires `OPENRAG_API_KEY` to be configured on the server — if it isn't, the request fails with `500`.

Path params:
- `filename` (string)

Response:
```json
{"filename": "string", "deleted_chunks": 0, "success": true}
```

If OpenRAG reports the delete as unsuccessful (e.g. the filename isn't ingested), the request fails with `404`.

## CSV

### `GET /csv`
Return the currently loaded CSV as JSON. Send header `Accept: text/csv` to get a raw file download instead. If no CSV is loaded, fails with `404`.

Response (JSON form):
```json
{"filename": "string", "content": "string"}
```

### `POST /csv`
Load a new CSV into server state, replacing whatever was loaded before.

Request: `multipart/form-data`, one part named `file`, sent as an actual file part (not a plain form field) — if it isn't, the request fails with `422`. The server derives the stored filename from the part's filename; if the part is sent with an empty filename, the request still succeeds but `filename` comes back as `""`. The file's contents must be valid UTF-8 text — if they aren't, the request fails with `422`.

Response:
```json
{"filename": "string", "content": "string"}
```

### `DELETE /csv`
Clear the loaded CSV only — leaves the chat session untouched, so chat history/context isn't lost just because the CSV was reset.

Response: `204 No Content`

## Chat

### `POST /chat`
Send an instruction to the LLM against the current CSV (if one is loaded). If the reply contains a fenced CSV block, it replaces the server's stored CSV state and is returned in `csv`; otherwise `csv` is `null`.

Request:
```json
{"instruction": "string"}
```

Response:
```json
{"response": "string", "csv": "string"}
```

### `DELETE /chat`
Rotate the session_id, resetting Langflow chat memory/context only — leaves the loaded CSV untouched.

Response: `204 No Content`
