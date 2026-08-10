'use client';

import { useState } from 'react';
import { Chat } from '@/components/Chat';
import { CsvPanel } from '@/components/CsvPanel';
import { Documents } from '@/components/Documents';

export default function Home() {
  const [csv, setCsv] = useState<string | null>(null);
  const [clearChatSignal, setClearChatSignal] = useState(0);

  async function handleClearChat() {
    const res = await fetch('/api/chat', { method: 'DELETE' });
    if (res.ok) {
      setClearChatSignal((s) => s + 1);
    }
  }

  return (
    <main className="grid grid-cols-2 gap-4 h-screen p-4 overflow-hidden">
      <div className="grid gap-4 min-h-0" style={{ gridTemplateRows: '1fr 2fr' }}>
        <Documents onClearChat={handleClearChat} />
        <Chat onCsvUpdate={setCsv} clearSignal={clearChatSignal} />
      </div>
      <CsvPanel csv={csv} setCsv={setCsv} />
    </main>
  );
}
