'use client';

import { useState } from 'react';
import { Chat } from '@/components/Chat';
import { CsvPanel } from '@/components/CsvPanel';
import { Documents } from '@/components/Documents';

export default function Home() {
  const [csv, setCsv] = useState<string | null>(null);

  return (
    <main className="grid grid-cols-3 gap-4 h-screen p-4">
      <CsvPanel csv={csv} setCsv={setCsv} />
      <Documents />
      <Chat onCsvUpdate={setCsv} />
    </main>
  );
}
