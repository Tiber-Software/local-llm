'use client';

import { useState } from 'react';
import { Chat } from '@/components/Chat';
import { CsvPanel } from '@/components/CsvPanel';

export default function Home() {
  const [csv, setCsv] = useState<string | null>(null);

  return (
    <main className="grid grid-cols-2 gap-4 h-screen p-4">
      <CsvPanel csv={csv} setCsv={setCsv} />
      <Chat onCsvUpdate={setCsv} />
    </main>
  );
}
