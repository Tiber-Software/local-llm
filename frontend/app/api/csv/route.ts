import { NextRequest } from 'next/server';

const BACKEND_URL = process.env.CSV_EDITOR_BACKEND_URL ?? 'http://localhost:3000';

export async function GET() {
  const res = await fetch(`${BACKEND_URL}/csv`, {
    headers: { Accept: 'application/json' },
  });
  const body = await res.text();
  return new Response(body, {
    status: res.status,
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const res = await fetch(`${BACKEND_URL}/csv`, { method: 'POST', body: formData });
  const body = await res.text();
  return new Response(body, {
    status: res.status,
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function DELETE() {
  const res = await fetch(`${BACKEND_URL}/csv`, { method: 'DELETE' });
  return new Response(null, { status: res.status });
}
