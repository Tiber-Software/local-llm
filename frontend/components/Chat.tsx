'use client';

import { useChat } from '@ai-sdk/react';
import { useState } from 'react';

export function Chat({ onCsvUpdate }: { onCsvUpdate: (csv: string) => void }) {
  const [input, setInput] = useState('');
  const { messages, sendMessage, status } = useChat({
    api: '/api/chat',
    onData: (part) => {
      if (part.type === 'data-csv') {
        onCsvUpdate((part.data as { content: string }).content);
      }
    },
  });

  return (
    <div className="flex flex-col h-full gap-4">
      <div className="flex-1 overflow-y-auto space-y-2">
        {messages.map((m) => (
          <div key={m.id} className={m.role === 'user' ? 'text-right' : 'text-left'}>
            <span
              className={`inline-block rounded-lg px-3 py-2 ${
                m.role === 'user' ? 'bg-blue-100' : 'bg-gray-100'
              }`}
            >
              {m.parts
                .filter((p): p is { type: 'text'; text: string } => p.type === 'text')
                .map((p, i) => (
                  <span key={i}>{p.text}</span>
                ))}
            </span>
          </div>
        ))}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!input.trim()) return;
          sendMessage({ text: input });
          setInput('');
        }}
        className="flex gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask the assistant to edit the CSV..."
          className="flex-1 border rounded px-3 py-2"
          disabled={status !== 'ready'}
        />
        <button
          type="submit"
          className="rounded bg-black text-white px-4 py-2 disabled:bg-gray-400"
          disabled={status !== 'ready'}
        >
          Send
        </button>
      </form>
    </div>
  );
}
