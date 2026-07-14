# CSV Editor REST API

Base URL: `http://localhost:5000`

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

Request: `multipart/form-data`
- `file`: document to upload (binary)

Query params:
- `wait` (boolean, default `false`)

Response (`202`):
```json
{"filename": "string", "task_id": "string", "status": "string"}
```

### `DELETE /documents/{filename}`
Remove a document (and all its chunks) from OpenRAG by filename.

Path params:
- `filename` (string)

Response:
```json
{"filename": "string", "deleted_chunks": 0, "success": true}
```

## CSV

### `GET /csv`
Return the currently loaded CSV as JSON. Send header `Accept: text/csv` to get a raw file download instead.

Response (JSON form):
```json
{"filename": "string", "content": "string"}
```

### `POST /csv`
Load a new CSV into server state, replacing whatever was loaded before.

Request: `multipart/form-data`
- `file`: CSV to upload (binary)

Response:
```json
{"filename": "string", "content": "string"}
```

### `DELETE /csv`
Clear the loaded CSV only — leaves the chat session untouched, so chat history/context isn't lost just because the CSV was reset.

Response: `204 No Content`

## Chat

### `POST /chat`
Send an instruction to the LLM against the current CSV. If the reply contains a fenced CSV block, it replaces the server's stored CSV state.

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
