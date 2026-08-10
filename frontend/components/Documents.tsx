'use client';

import { useEffect, useState } from 'react';

type Doc = {
  filename: string;
  chunks: number;
  source: string;
  mimetype: string;
  indexed_time: string;
  status: string;
};

export function Documents({ onClearChat }: { onClearChat?: () => void }) {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    loadDocs();
  }, []);

  useEffect(() => {
    const hasProcessing = docs.some((d) => d.status === 'processing');
    if (!hasProcessing) return;

    const interval = setInterval(() => {
      loadDocs();
    }, 2000);

    return () => clearInterval(interval);
  }, [docs]);

  async function loadDocs() {
    try {
      const res = await fetch('/api/documents');
      if (res.ok) {
        const data = await res.json();
        const serverDocs = data.documents || [];
        setDocs((current) => {
          const merged = [...current];
          for (const serverDoc of serverDocs) {
            const idx = merged.findIndex((d) => d.filename === serverDoc.filename);
            if (idx >= 0) {
              merged[idx] = serverDoc;
            } else {
              merged.push(serverDoc);
            }
          }
          return merged;
        });
      }
    } catch (err) {
      console.error('Failed to load documents', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch('/api/documents', { method: 'POST', body: form });
      if (res.ok) {
        const data = await res.json();
        setDocs((d) => [
          ...d,
          {
            filename: data.filename,
            chunks: 0,
            source: 'upload',
            mimetype: file.type || 'unknown',
            indexed_time: new Date().toISOString(),
            status: data.status,
          },
        ]);
      }
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  }

  async function handleDelete(filename: string) {
    if (!confirm(`Delete "${filename}"?`)) return;
    try {
      const res = await fetch(`/api/documents?filename=${encodeURIComponent(filename)}`, {
        method: 'DELETE',
      });
      if (!res.ok) {
        console.error('Delete failed:', res.status);
        return;
      }
      setDocs((d) => d.filter((doc) => doc.filename !== filename));
    } catch (err) {
      console.error('Failed to delete document', err);
    }
  }

  return (
    <div className="flex flex-col gap-2 h-full min-h-0">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <label className="cursor-pointer rounded bg-blue-200 px-3 py-1 text-sm hover:bg-blue-300 disabled:bg-gray-300">
            Upload
            <input
              type="file"
              className="hidden"
              onChange={handleUpload}
              disabled={uploading}
            />
          </label>
          <button
            onClick={() => setExpanded(!expanded)}
            className="rounded bg-gray-200 px-2 py-0.5 text-sm hover:bg-gray-300"
          >
            {expanded ? '▼' : '▶'} Documents ({docs.length})
          </button>
        </div>
        {onClearChat && (
          <button
            onClick={onClearChat}
            className="rounded bg-gray-200 px-3 py-1 text-sm hover:bg-gray-300"
          >
            Clear
          </button>
        )}
      </div>
      {expanded && (
        <>
          {loading ? (
            <p className="text-gray-500 text-sm">Loading…</p>
          ) : docs.length === 0 ? (
            <p className="text-gray-500 text-sm">No documents uploaded yet</p>
          ) : (
            <div className="flex-1 overflow-y-auto space-y-1 border rounded p-2 min-h-0">
              {docs.map((doc) => (
                <div key={doc.filename} className="flex items-start justify-between gap-2 text-sm border-b pb-1">
                  <div className="flex-1 min-w-0">
                    <p className="font-mono text-xs truncate">{doc.filename}</p>
                    <p className="text-xs text-gray-600">
                      {doc.chunks === 0 && doc.status === 'processing' ? 'ingesting...' : `${doc.chunks} chunks`} • {doc.mimetype}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDelete(doc.filename)}
                    className="rounded bg-red-100 px-2 py-0.5 text-xs hover:bg-red-200 flex-shrink-0"
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
