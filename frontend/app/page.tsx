'use client';

import { useState } from 'react';
import { Chat } from '@/components/Chat';
import { CsvPanel } from '@/components/CsvPanel';
import { Documents } from '@/components/Documents';

export default function Home() {
  const [csv, setCsv] = useState<string | null>(null);

  return (
    <main className="grid grid-cols-2 gap-4 h-screen p-4">
      <div className="grid gap-4" style={{ gridTemplateRows: '1fr 2fr' }}>
        <Documents />
        <Chat onCsvUpdate={setCsv} />
      </div>
      <CsvPanel csv={csv} setCsv={setCsv} />
    </main>
  );
}
