'use client';

import { useEffect, useRef, useState } from 'react';

type Message = { id: string; role: 'user' | 'assistant'; text: string };

export function Chat({ onCsvUpdate, clearSignal }: { onCsvUpdate: (csv: string) => void; clearSignal?: number }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (clearSignal) {
      setMessages([]);
    }
  }, [clearSignal]);

  useEffect(() => {
    if (!busy) {
      textareaRef.current?.focus();
    }
  }, [busy]);

  async function send() {
    if (!input.trim()) return;
    const userMsg: Message = { id: crypto.randomUUID(), role: 'user', text: input };
    setMessages((m) => [...m, userMsg]);
    setInput('');
    setBusy(true);
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [
            ...messages.map((m) => ({ role: m.role, parts: [{ type: 'text', text: m.text }] })),
            { role: 'user', parts: [{ type: 'text', text: userMsg.text }] },
          ],
        }),
      });
      if (!res.ok) {
        setMessages((m) => [...m, { id: crypto.randomUUID(), role: 'assistant', text: `Error: ${res.status}` }]);
        return;
      }
      const reader = res.body?.getReader();
      if (!reader) return;
      let assistantText = '';
      let csvUpdated = false;
      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (!line.startsWith('data:')) continue;
          const data = line.slice(5).trim();
          if (!data) continue;
          try {
            const parsed = JSON.parse(data);
            if (parsed.type === 'text-delta') {
              assistantText += parsed.delta;
            } else if (parsed.type === 'data-csv') {
              onCsvUpdate((parsed.data as { content: string }).content);
              csvUpdated = true;
            }
          } catch {
            // ignore parsing errors
          }
        }
      }
      if (assistantText) {
        const displayText = csvUpdated ? `✓ ${assistantText}` : assistantText;
        setMessages((m) => [...m, { id: crypto.randomUUID(), role: 'assistant', text: displayText }]);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col h-full gap-4">
      <div className="flex-1 overflow-y-auto space-y-2">
        {messages.map((m) => (
          <div key={m.id} className={m.role === 'user' ? 'text-right' : 'text-left'}>
            <span
              className={`inline-block rounded-lg px-3 py-2 ${m.role === 'user' ? 'bg-blue-100' : 'bg-gray-100'}`}
            >
              {m.text}
            </span>
          </div>
        ))}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
        className="flex gap-2"
      >
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          placeholder="Ask the assistant to edit the CSV..."
          className="flex-1 border rounded px-3 py-2 resize-none"
          disabled={busy}
          rows={3}
        />
        <button type="submit" className="rounded bg-black text-white px-4 py-2 disabled:bg-gray-400" disabled={busy}>
          {busy ? 'Sending…' : 'Send'}
        </button>
      </form>
    </div>
  );
}
