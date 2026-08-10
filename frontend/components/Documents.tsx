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

export function Documents() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    loadDocs();
  }, []);

  async function loadDocs() {
    try {
      const res = await fetch('/api/documents');
      if (res.ok) {
        const data = await res.json();
        setDocs(data.documents || []);
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
        await loadDocs();
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
      if (res.ok) {
        await loadDocs();
      }
    } catch (err) {
      console.error('Failed to delete document', err);
    }
  }

  return (
    <div className="flex flex-col gap-2 h-full">
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
        <h2 className="font-semibold">Documents ({docs.length})</h2>
      </div>
      {loading ? (
        <p className="text-gray-500">Loading…</p>
      ) : docs.length === 0 ? (
        <p className="text-gray-500 text-sm">No documents uploaded yet</p>
      ) : (
        <div className="flex-1 overflow-y-auto space-y-1 border rounded p-2">
          {docs.map((doc) => (
            <div key={doc.filename} className="flex items-start justify-between gap-2 text-sm border-b pb-1">
              <div className="flex-1 min-w-0">
                <p className="font-mono text-xs truncate">{doc.filename}</p>
                <p className="text-xs text-gray-600">{doc.chunks} chunks • {doc.mimetype}</p>
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
    </div>
  );
}
