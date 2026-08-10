'use client';

import { useEffect, useState } from 'react';

function parseCsv(content: string): string[][] {
  const rows: string[][] = [];
  let currentRow: string[] = [];
  let currentField = '';
  let insideQuotes = false;

  for (let i = 0; i < content.length; i++) {
    const char = content[i];
    const nextChar = content[i + 1];

    if (char === '"') {
      if (insideQuotes && nextChar === '"') {
        currentField += '"';
        i++;
      } else {
        insideQuotes = !insideQuotes;
      }
    } else if (char === ',' && !insideQuotes) {
      currentRow.push(currentField.trim());
      currentField = '';
    } else if ((char === '\n' || char === '\r') && !insideQuotes) {
      if (currentField || currentRow.length > 0) {
        currentRow.push(currentField.trim());
        if (currentRow.some((f) => f)) {
          rows.push(currentRow);
        }
        currentRow = [];
        currentField = '';
      }
      if (char === '\r' && nextChar === '\n') {
        i++;
      }
    } else {
      currentField += char;
    }
  }

  if (currentField || currentRow.length > 0) {
    currentRow.push(currentField.trim());
    if (currentRow.some((f) => f)) {
      rows.push(currentRow);
    }
  }

  return rows;
}

export function CsvPanel({ csv, setCsv }: { csv: string | null; setCsv: (v: string | null) => void }) {
  const [filename, setFilename] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/csv')
      .then(async (res) => (res.status === 404 ? null : res.ok ? res.json() : Promise.reject(res.status)))
      .then((data) => {
        if (data) {
          setCsv(data.content);
          setFilename(data.filename);
        }
      })
      .catch((err) => console.error('GET /api/csv failed', err))
      .finally(() => setLoading(false));
  }, [setCsv]);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    const res = await fetch('/api/csv', { method: 'POST', body: form });
    if (res.ok) {
      const data = await res.json();
      setCsv(data.content);
      setFilename(data.filename);
    }
    e.target.value = '';
  }

  async function handleClear() {
    const res = await fetch('/api/csv', { method: 'DELETE' });
    if (res.ok) {
      setCsv(null);
      setFilename(null);
    }
  }

  function handleDownload() {
    if (!csv) return;
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || 'export.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-col gap-2 h-full overflow-hidden min-h-0">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">{filename ?? 'No CSV loaded'}</h2>
        <div className="flex gap-2">
          <label className="cursor-pointer rounded bg-gray-200 px-3 py-1 text-sm hover:bg-gray-300">
            Upload CSV
            <input type="file" accept=".csv" className="hidden" onChange={handleUpload} />
          </label>
          {csv && (
            <>
              <button
                onClick={handleDownload}
                className="rounded bg-green-200 px-3 py-1 text-sm hover:bg-green-300"
              >
                Download
              </button>
              <button
                onClick={handleClear}
                className="rounded bg-red-200 px-3 py-1 text-sm hover:bg-red-300"
              >
                Clear
              </button>
            </>
          )}
        </div>
      </div>
      {loading ? (
        <p className="text-gray-500">Loading…</p>
      ) : csv ? (
        <div className="flex-1 overflow-auto border rounded min-h-0 bg-white">
          <table className="w-full border-collapse text-sm">
            <tbody>
              {parseCsv(csv).map((row, rowIdx) => (
                <tr key={rowIdx} className={rowIdx === 0 ? 'bg-gray-100' : rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                  {row.map((cell, cellIdx) => (
                    <td
                      key={cellIdx}
                      className="border border-gray-300 px-3 py-2 font-mono text-xs whitespace-nowrap overflow-hidden text-overflow-ellipsis"
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center border rounded bg-gray-50 text-gray-400">
          No CSV loaded
        </div>
      )}
    </div>
  );
}
